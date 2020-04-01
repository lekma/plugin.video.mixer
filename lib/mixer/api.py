# -*- coding: utf-8 -*-


from __future__ import absolute_import, division, unicode_literals


import requests
import m3u8

from six.moves.urllib.parse import urljoin

from . import objects
from ..utils import StreamQuality, notify, debug


class MixerSession(requests.Session):

    def __init__(self, headers=None):
        super(MixerSession, self).__init__()
        if headers:
            self.headers.update(headers)

    def request(self, *args, **kwargs):
        response = super(MixerSession, self).request(*args, **kwargs)
        response.raise_for_status()
        return response


class MixerService(object):

    _headers_ = {}

    _url_ = "https://mixer.com/api/"

    _urls_ = {
        "manifest": "v1/channels/{}/manifest.m3u8",
        "home": "v1/delve/home",
        "top_streams": "v1/delve/topStreams",
        "channels": "v1/channels",
        "channel": "v1/channels/{}",
        "games": "v1/types",
        "game": "v1/types/{}",
        "vods": "v2/vods/channels/{}",
        "vod": "v2/vods/{}"
    }

    _default_order_ = "viewersCurrent:DESC"

    def __init__(self):
        self.session = MixerSession(headers=self._headers_)
        self.game_cache = objects.Cache(self._games_())

    def query(self, url, **kwargs):
        return self.session.get(urljoin(self._url_, url), params=kwargs).json()

    # --------------------------------------------------------------------------

    def _stream_url_(self, id, quality=0):
        url = urljoin(self._url_, self._urls_["manifest"].format(id))
        if quality and quality < 7:
            manifest = m3u8.loads(self.session.get(url).text)
            qualities = [StreamQuality(playlist)
                         for playlist in manifest.playlists
                         if playlist.stream_info.resolution]
            qualities.sort(key=lambda x: x.height, reverse=True) # see Quality.best_match
            if quality == 6: # always ask
                selected = StreamQuality.select(qualities)
            else: # set quality
                selected = StreamQuality.best_match(quality, qualities)
            if selected < 0:
                return None
            url = qualities[selected].uri
        return url

    def stream_item(self, id, quality=0, **kwargs):
        stream = objects.Stream(self._get_channel_(id, **kwargs))
        if not stream.online:
            return notify(30016, stream.token) # Offline
        url = self._stream_url_(id, quality)
        return stream._item(url) if url else None

    def vod_item(self, id, quality=0, **kwargs):
        vod = objects.Vod(self._get_vod_(id, **kwargs))
        url = vod.url(quality)
        return vod._item(url) if url else None

    # --------------------------------------------------------------------------

    def _where_id_in_(self, ids):
        return ":".join(("id", "in", ";".join(map(str, ids))))

    def _get_home_(self, **kwargs):
        return self.query(self._urls_["home"], **kwargs)["rows"]

    def _delve_(self, _type, style, **kwargs):
        keys = kwargs.pop("keys", ("hydration", "results"))
        for row in self._get_home_(hydrate="true", **kwargs):
            if row["type"] == _type and row.get("style", "") == style:
                results = row
                for k in keys:
                    results = results.get(k, {})
                return (result["id"] for result in results)
        return []

    def _top_streams_(self, **kwargs):
        return self.query(self._urls_["top_streams"], **kwargs)

    def _get_channels_(self, **kwargs):
        kwargs.setdefault("page", 0)
        kwargs.setdefault("order", self._default_order_)
        return self.query(self._urls_["channels"], **kwargs)

    def _get_channel_(self, id, **kwargs):
        return self.query(self._urls_["channel"].format(id), **kwargs)

    def _get_vods_(self, id, **kwargs):
        return self.query(self._urls_["vods"].format(id), **kwargs)

    def _get_vod_(self, id, **kwargs):
        return self.query(self._urls_["vod"].format(id), **kwargs)

    def _get_games_(self, **kwargs):
        kwargs["noCount"] = "true"
        kwargs.setdefault("page", 0)
        kwargs.setdefault("order", self._default_order_)
        return self.query(self._urls_["games"], **kwargs)

    def _get_game_(self, id, **kwargs):
        return self.query(self._urls_["game"].format(id))

    # see objects.Vod ----------------------------------------------------------

    def _games_(self, limit=0, **kwargs):
        return objects.Games(self._get_games_(limit=limit, **kwargs),
                             limit=limit)

    def games(self, **kwargs):
        games = self._games_(**kwargs)
        self.game_cache.update(games)
        return games

    def _game_(self, id):
        game = objects.GameType(self._get_game_(id))
        self.game_cache[id] = game
        return game

    def game(self, id):
        try:
            return self.game_cache[id]
        except KeyError:
            return self._game_(id)

    # --------------------------------------------------------------------------

    def home(self, **kwargs):
        return objects.Home(self._get_home_(**kwargs))

    def featured(self, **kwargs):
        results = self._delve_("carousel", "", keys=("channels",), **kwargs)
        if results:
            results = self._get_channels_(where=self._where_id_in_(results))
        return objects.Streams(results)

    def spotlight(self, **kwargs):
        results = self._delve_("channels", "onlyOnMixer", **kwargs)
        if results:
            results = self._get_channels_(where=self._where_id_in_(results))
        return objects.Channels(results)

    def top_games(self, **kwargs):
        results = self._delve_("games", "", **kwargs)
        if results:
            return self.games(where=self._where_id_in_(results))
        return objects.Games(results, limit=limit)

    def up_and_coming(self, **kwargs):
        results = self._delve_("channels", "upAndComing", **kwargs)
        if results:
            where = self._where_id_in_(results)
            order = "online:DESC,createdAt:DESC"
            results = self._get_channels_(where=where, order=order)
        return objects.Streams(results)

    def top_streams(self, **kwargs):
        results = self._top_streams_(**kwargs)
        if results:
            where = self._where_id_in_((result["id"] for result in results))
            results = self._get_channels_(where=where)
        return objects.TopStreams(results)

    # --------------------------------------------------------------------------

    def browse_channels(self, limit=0, **kwargs):
        return objects.Channels(
            self._get_channels_(limit=limit, **kwargs), limit=limit)

    def browse_channel(self, **kwargs):
        id = kwargs.pop("id")
        stream = objects.Stream(self._get_channel_(id, **kwargs))
        return (stream, objects.Vods(self._get_vods_(id, **kwargs),
                                     category=stream.token))

    def browse_games(self, **kwargs):
        return self.games(**kwargs)

    def browse_game(self, limit=0, **kwargs):
        id = kwargs.pop("id")
        where = "typeId:eq:{}".format(id)
        return objects.Streams(
            self._get_channels_(where=where, limit=limit, **kwargs),
            limit=limit, category=self.game(id).name)

    # --------------------------------------------------------------------------

    def search_channels(self, query, limit=0, **kwargs):
        where = "suspended:eq:false,vodsEnabled:eq:true"
        order = "viewersCurrent:DESC,viewersTotal:DESC,token:ASC"
        scope = "names"
        return objects.Channels(
            self._get_channels_(where=where, order=order, scope=scope,
                                q=query, limit=limit, **kwargs),
            limit=limit)

    def search_games(self, query, limit=0, **kwargs):
        results = self._get_games_(query=query, limit=limit, **kwargs)
        if results:
            where = self._where_id_in_((result["id"] for result in results))
            order = "viewersCurrent:DESC,name:ASC"
            return self.games(where=where, order=order, limit=limit)
        return objects.Games(results, limit=limit)


service = MixerService()

