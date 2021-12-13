from __future__ import absolute_import, division, print_function
import sys
from typing import Optional
 #2017  pip3 install pycliarr==1.0.14
 #2018  pip3 install trakt.py

from trakt import Trakt

import schedule
import time

from threading import Condition
import logging
import os
import json
from datetime import datetime, timedelta

import re
import html
import pprint

from tmdbv3api import TMDb
from tmdbv3api import Account
from tmdbv3api import Authentication
from tmdbv3api import Discover, Genre, Movie
from tmdbv3api.tmdb import TMDb
from tmdbv3api.as_obj import AsObj

from threading import Condition

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.DEBUG)

config = {}

pp = pprint.PrettyPrinter(indent=2)

class watch_providers(TMDb):
    _urls = {
        "providers": "/movie/%s/watch/providers"
    }
    
    def providers(self, movie_id):
        """
        Watch Providers
        :param movie_id:
        :return:
        """
        return AsObj(**self._call(self._urls["providers"] % movie_id, ""))


# Python program to illustrate the intersection
# of two lists in most simple way
def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

class Application(object):
    def __init__(self):
        self.is_authenticating = Condition()

        self.authorization = None
        
        # Bind trakt events
        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

    def authenticate(self):
        if not self.is_authenticating.acquire(blocking=False):
            logging.info('Authentication has already been started')
            return False

        # Request new device code
        code = Trakt['oauth/device'].code()

        print('Enter the code "%s" at %s to authenticate your account' % (
            code.get('user_code'),
            code.get('verification_url')
        ))

        # Construct device authentication poller
        poller = Trakt['oauth/device'].poll(**code)\
            .on('aborted', self.on_aborted)\
            .on('authenticated', self.on_authenticated)\
            .on('expired', self.on_expired)\
            .on('poll', self.on_poll)

        # Start polling for authentication token
        poller.start(daemon=False)

        # Wait for authentication to complete
        return self.is_authenticating.wait()

    def run(self):
        if not self.authorization:
          self.authenticate()

        if not self.authorization:
            logging.error('ERROR: Authentication required')
            exit(1)
     
        #STrakt.configuration.oauth.from_response(self.authorization)   
        Trakt.configuration.defaults.oauth.from_response(self.authorization, refresh=True)
        tmdb = TMDb()
        tmdb.api_key = config["tmdb"]["api_key"]
        auth = Authentication(username=config["tmdb"]["user"], password=config["tmdb"]["password"])
        account = Account()
        details = account.details()
        logging.info("You are logged in to tmdb as %s. Your account ID is %s." % (details.username, details.id))

        logging.info("Retrieve watched from trakt")
        # ('imdb', 'tt1815862'): <Movie 'After Earth' (2013)>
        watched = {}
        Trakt['sync/watched'].movies(watched, exceptions=True)
        #pp.pprint(watched)

        tmdb_in_watched = [
                int(id[1])
                for k,m in watched.items()
                for id in m.keys
                if id[0] == "tmdb"
        ]
        assert(len(watched)==len(tmdb_in_watched))
        #logging.debug("Movies tmdb ids of watched movies: {}".format(pprint.pformat(tmdb_in_watched)))
        logging.info("Retrieve movies in list [{}]".format(config["trakt"]["list"]))
        trakt_in_list = Trakt['users/*/lists/*'].items(
                            config["trakt"]["user"],
                            config["trakt"]["list"],
                            media="movies",
                            exceptions=True
                            )
        #pp.pprint(trakt_in_list)
        if not trakt_in_list:
            raise(Exception("can't retrieve list movies from Trakt"))
        
        tmdb_in_list = [
                int(id[1])
                for m in trakt_in_list
                for id in m.keys
                if id[0] == "tmdb"
        ]
        #logging.debug("Tmdb list of movies in list {}".format(pprint.pformat(tmdb_in_list)))

        genre = Genre()
        mov = Movie()
        tmdb_list = []        
        genres = genre.movie_list()
        discover = Discover()
        excluded_count = 0

        for fil in config["filters"]["filter_list"]:
            discovered = discover.discover_movies( {
                "primary_release_date.gte": "{}-01-01".format(config["filters"]["from_year"]),
                "vote_count.gte": fil["imdb_people"],
                "vote_average.gte": fil["imdb_range"][0],  
                "vote_average.lte": fil["imdb_range"][1],  
                "sort_by": "release_date.desc",  
                })
            logging.info("{} movies discovered in votes range: {}".format(len(discovered), fil["imdb_range"]))
            for movie in discovered:
                #ext_id = mov.external_ids(movie.id)
                #if "imdb" not in ext_id:
                #    continue

                if movie.id in tmdb_in_list or movie.id in tmdb_in_watched:
                    logging.debug("{} already watched or marked in the list. Excluded.".format(movie.title))
                    excluded_count += 1
                    continue
                
                movie_genres = [
                        gen.name
                        for gen in genres
                        if gen.id in movie.genre_ids
                ]
                if not ((len(fil["include_genres"]) == 0 or 
                        len(intersection(movie_genres , fil["include_genres"])) > 0 ) \
                      and ( len(fil["exclude_genres"]) == 0 or 
                              len(intersection(movie_genres, fil["exclude_genres"])) == 0 )):
                    logging.debug("{} will not be added to the Trakt list because genres don't match: {}".format(movie.title, movie_genres ))
                    excluded_count += 1
                    continue

                if fil["exclude_providers_for_country"]: 
                    prov = watch_providers()
                    prov_list = prov.providers(movie.id)
                    if fil["exclude_providers_for_country"] not in prov_list.get("results", {}):
                        logging.debug("{} will not be added to the Trakt list because there aren't a country that match configuration: {}".format(movie.title,  fil["exclude_providers_for_country"] ))
                        excluded_count += 1
                        continue
                    logging.debug(pprint.pformat(prov_list["results"][fil["exclude_providers_for_country"] ], indent=2))
                    comps = [c["provider_name"] for c in prov_list["results"][ fil["exclude_providers_for_country"] ].get("flatrate", [])]
                    if comps and len(intersection(fil["exclude_providers"], comps)) > 0:
                        logging.debug("{} will not be added to the Trakt list because provider is excluded: {}".format(movie.title, comps))
                        excluded_count += 1
                        continue

                logging.info("{} will be added to the Trakt list ({}({}) - genres: {} - pop: {} {}/{} - {})".format(
                        movie.id, movie.title, movie.release_date, movie_genres, movie.popularity, movie.vote_average, movie.vote_count, comps 
                        ))
                    
                tmdb_list.append(movie.id)

        logging.info("{} excluded by config filters".format(excluded_count))
        if len(tmdb_list) > 0:
            to_add = { "movies": [ 
                       {"ids": {
                           'tmdb': tmdb_list
                           }
                       }                 ]
            }
            logging.info("Add {} movies to list [{}]".format( len(tmdb_list), config["trakt"]["list"]))
            logging.debug(pprint.pformat(to_add))
            result = Trakt['users/*/lists/*'].add(
                                config["trakt"]["user"],
                                config["trakt"]["list"],
                                to_add,
                                exceptions=True
                                )
            logging.info("{} added to the list".format(result["added"]["movies"]))
            logging.info("not found: {}".format(pprint.pformat(result["not_found"]["movies"])))
        else:
            logging.info("No new movies to add.")
        
        logging.info("Finished =====")


    def on_aborted(self):
        """Device authentication aborted.

        Triggered when device authentication was aborted (either with `DeviceOAuthPoller.stop()`
        or via the "poll" event)
        """

        print('Authentication aborted')

        # Authentication aborted
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_authenticated(self, authorization):
        """Device authenticated.

        :param authorization: Authentication token details
        :type authorization: dict
        """

        # Acquire condition
        self.is_authenticating.acquire()

        # Store authorization for future calls
        self.authorization = authorization

        print('Authentication successful - authorization: %r' % self.authorization)

        # Authentication complete
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

        self.save_token()

    def on_expired(self):
        """Device authentication expired."""

        print('Authentication expired')

        # Authentication expired
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_poll(self, callback):
        """Device authentication poll.

        :param callback: Call with `True` to continue polling, or `False` to abort polling
        :type callback: func
        """

        # Continue polling
        callback(True)

    def on_token_refreshed(self, authorization):
        # OAuth token refreshed, store authorization for future calls
        self.authorization = authorization

        print('Token refreshed - authorization: %r' % self.authorization)
        self.save_token()

    def save_token(self):
        with open("config/authtoken.json", 'w') as outfile:
          json.dump(self.authorization, outfile)

def execute():
    app = Application()
    if os.path.exists("config/authtoken.json"):
        #authorization = os.environ.get('AUTHORIZATION')
        with open("config/authtoken.json", 'r') as file:
            app.authorization = json.load(file)
    app.run()

if __name__ == '__main__':
    #global config

    # Configure
    if not os.path.exists("config/config.json"):
        raise Exception("Error config.json not found")
    with open("config/config.json", 'r') as file:
        config  = json.load(file)
        #print(config)
    
    Trakt.base_url = config["trakt"]["base_url"]

    Trakt.configuration.defaults.client(
      id=config["trakt"]["id"],
      secret=config["trakt"]["secret"],
    )

    # first auth
    if not os.path.exists("config/authtoken.json"):
        print('auth...')
        app = Application()
        app.authenticate()
        if not os.path.exists("config/authtoken.json"):
            print('Auth failed!')
            sys.exit(-1)
    
    execute()
    
    logging.info("Waiting...")

    schedule.every(config["schedule_hours"]).hours.do(execute)
    while True:
        schedule.run_pending()
        #print("waiting...")
        time.sleep(60)  
