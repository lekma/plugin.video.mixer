# -*- coding: utf-8 -*-


from __future__ import absolute_import, division, unicode_literals


from six import wraps
from kodi_six import xbmc, xbmcplugin
from inputstreamhelper import Helper

from .utils import parse_query, get_setting, get_subfolders, more_item
from .utils import localized_string, search_dialog
from .mixer.api import service
from .mixer.objects import Folders


def action(category=0):
    def decorator(func):
        func.__action__ = True
        @wraps(func)
        def wrapper(self, **kwargs):
            try:
                self.category = category
                self.action = func.__name__
                success = func(self, **kwargs)
            except Exception:
                success = False
                raise
            finally:
                self.endDirectory(success)
                del self.action, self.category
        return wrapper
    return decorator


class Dispatcher(object):

    def __init__(self, url, handle):
        self.url = url
        self.handle = handle
        self.limit = get_setting("items_per_page", int)
        self.language = xbmc.getLanguage(xbmc.ISO_639_1)


    # utils --------------------------------------------------------------------

    def play(self, item, quality=0):
        if quality == 7: # inputstream.adaptive
            if not Helper("hls").check_inputstream():
                return False
            item.setProperty("inputstreamaddon", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
        xbmcplugin.setResolvedUrl(self.handle, True, item)
        return True

    def addItem(self, item):
        if item and not xbmcplugin.addDirectoryItem(self.handle, *item.asItem()):
            raise
        return True

    def addItems(self, items, *args, **kwargs):
        if not xbmcplugin.addDirectoryItems(
            self.handle, [item.asItem()
                          for item in items.items(self.url, *args) if item]):
            raise
        if items.more:
            self.addItem(more_item(self.url, action=self.action, **kwargs))
        if items.content:
            xbmcplugin.setContent(self.handle, items.content)
        if items.category:
            self.setCategory(items.category)
        return True

    def setCategory(self, category):
        xbmcplugin.setPluginCategory(self.handle, category)
        self.category = 0

    def endDirectory(self, success):
        if success and self.category:
            self.setCategory(localized_string(self.category))
        xbmcplugin.endOfDirectory(self.handle, success)


    # actions ------------------------------------------------------------------

    @action()
    def play_stream(self, **kwargs):
        quality = get_setting("stream_quality", int)
        item = service.stream_item(kwargs.pop("id"), quality, **kwargs)
        return self.play(item, quality) if item else False

    @action()
    def play_vod(self, **kwargs):
        quality = get_setting("vod_quality", int)
        item = service.vod_item(kwargs.pop("id"), quality, **kwargs)
        return self.play(item, quality) if item else False

    @action()
    def home(self, **kwargs):
        return self.addItems(service.home(**kwargs))

    @action(30007)
    def featured(self, **kwargs):
        return self.addItems(
            service.featured(language=self.language, **kwargs), "play_stream")

    @action(30009)
    def spotlight(self, **kwargs):
        return self.addItems(service.spotlight(**kwargs), "browse_channel")

    @action(30011)
    def top_games(self, **kwargs):
        return self.addItems(service.top_games(**kwargs), "browse_game")

    @action(30013)
    def up_and_coming(self, **kwargs):
        return self.addItems(service.up_and_coming(**kwargs), "play_stream")

    @action(30015)
    def top_streams(self, **kwargs):
        return self.addItems(
            service.top_streams(**kwargs), "play_stream", **kwargs)


    # browse -------------------------------------------------------------------

    @action(30001)
    def browse(self, **kwargs):
        return self.addItems(Folders(get_subfolders("browse"), **kwargs))

    @action(30003)
    def browse_channels(self, **kwargs):
        return self.addItems(
            service.browse_channels(limit=self.limit, **kwargs),
            "browse_channel", **kwargs)

    @action()
    def browse_channel(self, **kwargs):
        stream, vods = service.browse_channel(**kwargs)
        if stream:
            self.addItem(stream.item(self.url, "play_stream"))
        return self.addItems(vods, "play_vod")

    @action(30006)
    def browse_games(self, **kwargs):
        return self.addItems(
            service.browse_games(limit=self.limit, **kwargs),
            "browse_game", **kwargs)

    @action()
    def browse_game(self, **kwargs):
        return self.addItems(
            service.browse_game(limit=self.limit, **kwargs),
            "play_stream", **kwargs)


    # search -------------------------------------------------------------------

    @action(30002)
    def search(self, **kwargs):
        return self.addItems(Folders(get_subfolders("search"), **kwargs))

    @action(30003)
    def search_channels(self, **kwargs):
        query = kwargs.pop("query", "") or search_dialog()
        if query:
            return self.addItems(
                service.search_channels(query, limit=self.limit, **kwargs),
                "browse_channel", query=query, **kwargs)
        return False # failing here is a bit stupid

    @action(30006)
    def search_games(self, **kwargs):
        query = kwargs.pop("query", "") or search_dialog()
        if query:
            return self.addItems(
                service.search_games(query, limit=self.limit, **kwargs),
                "browse_game", query=query, **kwargs)
        return False # failing here is a bit stupid


    # dispatch -----------------------------------------------------------------

    def dispatch(self, **kwargs):
        action = getattr(self, kwargs.pop("action", "home"))
        if not callable(action) or not getattr(action, "__action__", False):
            raise Exception("Invalid action '{}'".format(action.__name__))
        return action(**kwargs)


def dispatch(url, handle, query, *args):
    Dispatcher(url, int(handle)).dispatch(**parse_query(query))

