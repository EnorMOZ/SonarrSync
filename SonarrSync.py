import os
import logging
import json
import sys
import requests
import configparser
import argparse
import shutil
import time

parser = argparse.ArgumentParser(description='SonarrSync. Sync two or more Sonarr servers.')
parser.add_argument('--config', action="store", type=str, help='Location of config file.')
parser.add_argument('--debug', help='Enable debug logging.', action="store_true")
parser.add_argument('--whatif', help="Read-Only. What would happen if I ran this. No posts are sent. Should be used with --debug", action="store_true")
args = parser.parse_args()

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
if args.config:
    settingsFilename = args.config
elif not os.path.isfile(settingsFilename):
    print("Creating default config. Please edit and run again.")
    shutil.copyfile(os.path.join(os.getcwd(), 'Config.default'), settingsFilename)
    sys.exit(0)
Config.read(settingsFilename)

print(ConfigSectionMap('Sonarr_4k')['rootfolders'].split(';'))
#exit()

########################################################################################################################
logger = logging.getLogger()
if ConfigSectionMap("General")['log_level'] == 'DEBUG':
    logger.setLevel(logging.DEBUG)
elif ConfigSectionMap("General")['log_level'] == 'VERBOSE':
    logger.setLevel(logging.VERBOSE)
else:
    logger.setLevel(logging.INFO)
if args.debug:
    logger.setLevel(logging.DEBUG)

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

fileHandler = logging.FileHandler(ConfigSectionMap('General')['log_path'],'w','utf-8')
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
########################################################################################################################

session = requests.Session()
session.trust_env = False

sonarr_url = ConfigSectionMap("SonarrMaster")['url']
sonarr_key = ConfigSectionMap("SonarrMaster")['key']
sonarrSeries = session.get('{0}/api/series?apikey={1}'.format(sonarr_url, sonarr_key))
if sonarrSeries.status_code != 200:
    logger.error('Master Sonarr server error - response {}'.format(sonarrSeries.status_code))
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
            for serie in series.json():
                servers[server]['series'].append(series['tvdbId'])

for serie in sonarrSeries.json():
    for name, server in servers.items():
        if serie['profileId'] == int(server['profileidmatch']):
            if serie['tvdbId'] not in server['series']:
                if 'rootfolders' in server:
                    allowedFolders = server['rootfolders'].split(';')
                    for folder in allowedFolders:
                        if not folder in serie['path']:
                            continue
                if 'replace_path' in server:
                    path = str(serie['path']).replace(server['replace_path'], server['new_path'])
                    logging.debug('Updating serie path from: {0} to {1}'.format(serie['path'], path))
                else:
                    path = serie['path']
                logging.debug('server: {0}'.format(name))
                logging.debug('title: {0}'.format(serie['title']))
                logging.debug('qualityProfileId: {0}'.format(server['profileid']))
                logging.debug('titleSlug: {0}'.format(serie['titleSlug']))
                images = serie['images']
                for image in images:
                    image['url'] = '{0}{1}'.format(sonarr_url, image['url'])
                    logging.debug(image['url'])
                logging.debug('tvdbId: {0}'.format(serie['tvdbId']))
                logging.debug('path: {0}'.format(path))
                logging.debug('monitored: {0}'.format(serie['monitored']))

                payload = {'title': serie['title'],
                           'qualityProfileId': server['profileid'],
                           'titleSlug': serie['titleSlug'],
                           'tvdbId': serie['tvdbId'],
                           'path': path,
                           'monitored': serie['monitored'],
                           'images': images,
                           'profileId': serie['profileId'],
                           'seasons': serie['seasons'],
                           'seasonFolder': serie['seasonFolder'],
                           'seriesType': serie['seriesType']
                           }

                logging.debug('payload: {0}'.format(payload))
                server['newSeries'] += 1
                if args.whatif:
                    logging.debug('WhatIf: Not actually adding serie to Sonarr {0}.'.format(name))
                else:
                    if server['newSeries'] > 0:
                        logging.debug('Sleeping for: {0} seconds.'.format(ConfigSectionMap('General')['wait_between_add']))
                        time.sleep(int(ConfigSectionMap('General')['wait_between_add']))
                    r = session.post('{0}/api/series?apikey={1}'.format(server['url'], server['key']), data=json.dumps(payload))
                    server['searchid'].append(int(r.json()['id']))
                logger.info('adding {0} to Sonarr {1} server'.format(serie['title'], name))
            else:
                logging.debug('{0} already in {1} library'.format(serie['title'], name))

for name, server in servers.items():
    if len(server['searchid']):
        payload = {'name' : 'SeriesSearch', 'seriesIds' : server['searchid']}
        session.post('{0}/api/command?apikey={1}'.format(server['url'], server['key']),data=json.dumps(payload))
