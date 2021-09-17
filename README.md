# tmdb-to-trakt
Explore new movies in TMDB and add them to a Trakt list based on a configured criteria

# Instalation

Download the code and copy it to a directory of your preference. 

# Requeriments

Please read the `requirements.txt` to understand the dependencies.

Run de requirements install:

```bash
pip3 install -r requirements.txt
```

# config.json

Create a json file (you can copy the `config.json.example` in the `config/` subdir).

```json
{
    "schedule_hours": 6,

    "channel_username": "MoviesTorrentsReleases",
    "filters": {
      "from_year": 2020,
      "filter_list": [ {
        "imdb_range": [5.5, 5.99],
        "imdb_people": 100,
        "include_genres": [ "Horror", "Sci-Fi" ],
        "exclude_genres": [ "Family", "Biography", "Comedy", "Animation", "Sports", "Documentary", "Biography", "Short" ],
        "exclude_providers": [ "Netflix" ],
        "exclude_providers_for_country": "AR"
      }, {
        "imdb_range": [6, 6.99],
        "imdb_people": 500,
        "include_genres": [ "Suspense","Thriller", "Horror", "Mystery", "Action", "Adventure", "Crime", "Sci-Fi" ],
        "exclude_genres": [ "Family", "Biography", "Animation", "Sports", "Documentary", "Short" ],
        "exclude_providers": [ "Netflix" ],
        "exclude_providers_for_country": "AR"
      }, {
        "imdb_range": [7, 100],
        "imdb_people": 1000,
        "include_genres": [],
        "exclude_genres": [ "Biography", "Animation", "Sports", "Documentary", "Short" ],
        "exclude_providers": [ "Netflix" ],
        "exclude_providers_for_country": "AR"
     }]
    },
    "trakt": {
        "base_url": "https://api.trakt.tv",
        "id": "Your trakt ID",
        "secret": "Your secret",
        "list": "list to add movies",
        "user": "Your user"
   },
  "tmdb": {
    "api_key": "The TMDb API Key",
    "user": "Your user",
    "password": "The password"
    }
}
```
* schedule_hours: time between executions
* filters: requeriments to select a movie.
    * from_year: ignore movies realased before this date.
    * filter_list: list of filters to apply (in order)
        * tmdb_range: from/to califications. A movie with califications between this range will be selected and added to the list.
        * tmdb_people: minimal quantity of people who voted.
        * include_genres: the movie must to have at least one of those genres. Empty means "all"
        * exclude_genres: if the movie has at least one of those will be exluded. Empty means "all"
        * exclude_providers_for_country: TMDb has information about the providers ordered by country, assign your country here, for example US, AR, etc
        * exclude_providers: if you want to exclude movies for a specific provider. Example: Netflix.
* trakt: 
    * trakt connection information (see below)
    * list: a trakt user list where you add the movies of intereset.
* tmdb: TMDb connection information (see below)

# Examples

In the configuration example above, a Drama movie with a calification of 8/17000 (17000 votes that result in a calification of eight) will be selected. Instead, if the movie is a Sport Drama will be excluded .

A Horror movie with a calification of 5.5/200 will be selected. The same but animation horror will be excluded. Usefull if you like Horror movies but not the Animation genre.

This configuration catches any movie with a calification 7/1000 or above. But exclude Shorts for example.

# Trakt

The `trakt.py` library needs to connect this application to Trakt, and to give permissions to your Trakt user. For that you will need to create a new application in Trakt to obtain your `id` and `secret`.

Goto https://trakt.tv/oauth/applications/new

Copy the id and secret to your `config.json`.

# TMDb

The script uses `tmdbv3api`, from https://github.com/AnthonyBloomer/tmdbv3api

Register an account: https://www.themoviedb.org/account/signup

Step by step in https://developers.themoviedb.org/3/getting-started/introduction

It's important to collect `api_key`, `user` and `password` to fill the `config.json` file in the `/config` folder.

At start, the program will ask for permission, it's look like this:

```
Enter the code "9A73X2F9" at https://trakt.tv/activate to authenticate your account
```
go to https://trakt.tv/activate, fill in with the code and assign the premission.

# Docker

A `dockerfile` is provided in order to use the program under docker.

## docker create image

`docker build -t telegram-to-trakt .`

## docker-compose example

```yaml
  tmdb_to_track:
    build:
      context: ./<folder where the software was copied>
    image: tmdb-to-trakt:latest
    volumes:
     - /home/<your user>/<folder where the software was copied>/config:/usr/src/app/config
    environment:
      TZ: America/Argentina/Buenos_Aires
    restart: unless-stopped

```
