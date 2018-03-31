import os
import logging
import json
import sys
import requests
import configparser


########################################################################################################################
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

fileHandler = logging.FileHandler("./Output.txt")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
########################################################################################################################

def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                logger.debug("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

Config = configparser.ConfigParser()
settingsFilename = os.path.join(os.getcwd(), 'Config.txt')
Config.read(settingsFilename)

session = requests.Session()
session.trust_env = False

radarr_url = ConfigSectionMap("RadarrMaster")['url']
radarr_key = ConfigSectionMap("RadarrMaster")['key']
radarrMovies = session.get('{0}/api/movie?apikey={1}'.format(radarr_url, radarr_key))
if radarrMovies.status_code != 200:
    logger.error('Master Radarr server error - response {}'.format(radarrMovies.status_code))
    sys.exit(0)

servers = {}
for section in Config.sections():
    section = str(section)
    if "Radarr_" in section:
        server = (str.split(section,'Radarr_'))[1]
        servers[server] = ConfigSectionMap(section)
        movies = session.get('{0}/api/movie?apikey={1}'.format(servers[server]['url'], servers[server]['key']))
        if movies.status_code != 200:
            logger.error('{0} Radarr server error - response {1}'.format(server, movies.status_code))
            sys.exit(0)
        else:
            servers[server]['movies'] = []
            servers[server]['newMovies'] = 0
            servers[server]['searchid'] = []
            for movie in movies.json():
                servers[server]['movies'].append(movie['tmdbId'])

for movie in radarrMovies.json():
    for name, server in servers.items():
        if movie['profileId'] == int(server['profileidmatch']):
            if movie['tmdbId'] not in server['movies']:
                path = str.replace(str(movie['path']), ConfigSectionMap("RadarrMaster")['basepath'], server['newpath'])
                logging.debug('server: {0}'.format(name))
                logging.debug('title: {0}'.format(movie['title']))
                logging.debug('qualityProfileId: {0}'.format(server['profileid']))
                logging.debug('titleSlug: {0}'.format(movie['titleSlug']))
                images = movie['images']
                for image in images:
                    image['url'] = '{0}{1}'.format(radarr_url, image['url'])
                    logging.debug(image['url'])
                logging.debug('tmdbId: {0}'.format(movie['tmdbId']))
                logging.debug('path: {0}'.format(path))
                logging.debug('monitored: {0}'.format(movie['monitored']))

                payload = {'title': movie['title'],
                           'qualityProfileId': server['profileid'],
                           'titleSlug': movie['titleSlug'],
                           'tmdbId': movie['tmdbId'],
                           'path': path,
                           'monitored': movie['monitored'],
                           'images': images,
                           'profileId': movie['profileId'],
                           'minimumAvailability': 'released'
                           }

                r = session.post('{0}/api/movie?apikey={1}'.format(server['url'], server['key']), data=json.dumps(payload))
                logging.debug('payload: {0}'.format(payload))
                server['searchid'].append(int(r.json()['id']))
                logger.info('adding {0} to Radarr {1} server'.format(movie['title'], name))
            else:
                logging.debug('{0} already in {1} library'.format(movie['title'], name))

for name, server in servers.items():
    if len(server['searchid']):
        payload = {'name' : 'MoviesSearch', 'movieIds' : server['searchid']}
        session.post('{0}/api/command?apikey={1}'.format(server['url'], server['key']),data=json.dumps(payload))

