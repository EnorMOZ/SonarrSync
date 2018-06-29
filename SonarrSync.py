import os
import logging
import json
import sys
import requests
import configparser


########################################################################################################################
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

fileHandler = logging.FileHandler("./Output.txt",'w','utf-8')
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

sonarr_url = ConfigSectionMap("SonarrMaster")['url']
sonarr_key = ConfigSectionMap("SonarrMaster")['key']
sonarrMovies = session.get('{0}/api/series?apikey={1}'.format(sonarr_url, sonarr_key))
if sonarrMovies.status_code != 200:
    logger.error('Master Sonarr server error - response {}'.format(sonarrMovies.status_code))
    sys.exit(0)

servers = {}
for section in Config.sections():
    section = str(section)
    if "Sonarr_" in section:
        server = (str.split(section,'Sonarr_'))[1]
        servers[server] = ConfigSectionMap(section)
        series = session.get('{0}/api/series?apikey={1}'.format(servers[server]['url'], servers[server]['key']))
        if series.status_code != 200:
            logger.error('{0} Sonarr server error - response {1}'.format(server, series.status_code))
            sys.exit(0)
        else:
            servers[server]['series'] = []
            servers[server]['newSeries'] = 0
            servers[server]['searchid'] = []
            for series in series.json():
                servers[server]['series'].append(series['tvdbId'])

for series in sonarrMovies.json():
    for name, server in servers.items():
        if series['profileId'] == int(server['profileidmatch']):
            if series['tvdbId'] not in server['series']:
                spath = ConfigSectionMap("SonarrMaster")['basepath']
                logging.debug('spath: {0}'.format(spath))
                if spath in series['path']:
                    rpath = str.replace(str(series['path']), ConfigSectionMap("SonarrMaster")['basepath'], server['newpath'])
                    logging.debug('server: {0}'.format(name))
                    logging.debug('newpath: {0}'.format(rpath))
                    logging.debug('title: {0}'.format(series['title']))
                    logging.debug('qualityProfileId: {0}'.format(server['profileid']))
                    logging.debug('titleSlug: {0}'.format(series['titleSlug']))
                    images = series['images']
                    for image in images:
                        image['url'] = '{0}{1}'.format(sonarr_url, image['url'])
                        logging.debug(image['url'])
                    logging.debug('tvdbId: {0}'.format(series['tvdbId']))
                    logging.debug('path: {0}'.format(rpath))
                    logging.debug('monitored: {0}'.format(series['monitored']))

                    payload = {'title': series['title'],
                               'qualityProfileId': server['profileid'],
                               'titleSlug': series['titleSlug'],
                               'tvdbId': series['tvdbId'],
                               'path': path,
                               'monitored': series['monitored'],
                               'images': images,
                               'profileId': series['profileId'],
                               'seasons': series['seasons'],
                               'seasonFolder': series['seasonFolder'],
                               'seriesType': series['seriesType']
                               }

                    r = session.post('{0}/api/series?apikey={1}'.format(server['url'], server['key']), data=json.dumps(payload))
                    logging.debug('payload: {0}'.format(payload))
                    server['searchid'].append(int(r.json()['id']))
                    logger.info('adding {0} to Sonarr {1} server'.format(series['title'], name))
            else:
                logging.debug('{0} already in {1} library'.format(series['title'], name))

for name, server in servers.items():
    if len(server['searchid']):
        payload = {'name' : 'SeriesSearch', 'seriesIds' : server['searchid']}
        session.post('{0}/api/command?apikey={1}'.format(server['url'], server['key']),data=json.dumps(payload))
