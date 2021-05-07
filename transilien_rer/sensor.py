"""Platform for sensor integration."""
from homeassistant.const import TIME_MINUTES
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

import logging
import datetime

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = datetime.timedelta(seconds=60)
# MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("id_rer"): cv.string,
        vol.Required("id_arret"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    id_rer = config.get("id_rer")
    id_arret = config.get("id_arret")

    # rer = [train(nb=nb_start+0), train(nb=nb_start+1), train(nb=nb_start+2)]

    rer = [train(nb=0, ligne=id_rer, arret=id_arret),
           train(nb=1, ligne=id_rer, arret=id_arret),
           train(nb=2, ligne=id_rer, arret=id_arret)
           ]

    if not rer:
        _LOGGER.error("Unable to connect to rer")
        return

    dev = []
    dev.append(ExampleSensor(rer[0], 'next'))
    dev.append(ExampleSensor(rer[1], 'next_1'))
    dev.append(ExampleSensor(rer[2], 'next_2'))

    add_entities(dev, True)


class ExampleSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, rer, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self.train = rer
        self.attr = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} RER'.format(self._name)

    @property
    def should_poll(self):
        """Permet de update"""
        return True

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:train"

    @property
    def scan_interval(self):
        """Return the unique id."""
        return SCAN_INTERVAL

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attr

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit of measurement."""
    #     return TIME_MINUTES

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        self.train.get_navigo()
        self.attr["time"] = self.train.time
        self.attr["destination"] = self.train.destination
        self.attr["message"] = self.train.msg

        if self.train.msg == 'RAS':
            self._state = str(self.train.time)
        elif self.train.msg == 'FIN DE SERVICE':
            self._state = self.train.msg
        else:
            self._state = self.train.msg


class train:

    def __init__(self, nb=0, ligne='C', arret='jouy_rer'):
        """Initialize the sensor."""
        self.destination = None
        self.time = None
        self.nb = nb
        self.msg = 'RAS'

        self.ligne = ligne
        self.stop = arret

        self.get_navigo()

    def autentification(self, ):
        # A faire au moins une fois par heure
        # -----------------------------------
        import requests, settings
        urlOAuth = 'https://as.api.iledefrance-mobilites.fr/api/oauth/token'
        client_id = settings.client_id,
        client_secret = settings.client_secret

        # Paramètres de la requête de demande de token
        data = dict(
            grant_type='client_credentials',
            scope='read-data',
            client_id=client_id,
            client_secret=client_secret
        )
        response = requests.post(urlOAuth, data=data)
        jsonData = response.json()
        return jsonData['access_token']

    def get_navigo(self):
        import requests
        from . import code_ligne

        token = self.autentification()
        url = 'https://traffic.api.iledefrance-mobilites.fr/v1/tr-vianavigo/departures'

        params = dict(
            line_id=code_ligne.rer[self.ligne],
            stop_point_id=code_ligne.arret[self.stop],
        )

        # on lance la requete
        response = requests.get(url, params=params, headers={'Authorization': 'Bearer ' + token})
        jsondata = response.json()

        if response.status_code == 404:
            # _LOGGER.warning("Reponse code %s" % response.status_code)
            self.time = 0
            self.msg = 'FIN DE SERVICE'
            return
        elif response.status_code == 200:
            pass
        else:
            _LOGGER.warning("Reponse code %s" % response.status_code)

        l_train = []

        for train_temp in jsondata:
            if "schedule" in train_temp.keys() and train_temp['schedule'] == 'Supprimé':
                continue
            else:
                l_train.append(train_temp)

        try:
            next = l_train[self.nb]
        except IndexError:
            _LOGGER.warning('Fin de service au numéro %s' % self.nb)
            return

        if 'time' in next.keys():
            self.time = next['time']
            self.msg = 'RAS'
        elif 'schedule' in next.keys():
            self.time = 0
            self.msg = next['schedule']
        else:
            print(next)

        self.destination = next['lineDirection']
        # print('Prochain RER numero %s direction %s dans %s min' %(self.nb, self.destination, self.time))