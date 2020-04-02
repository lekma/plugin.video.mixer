# -*- coding: utf-8 -*-


from __future__ import absolute_import, division, unicode_literals


import sys

from datetime import datetime
from uuid import UUID
from itertools import chain

from six import string_types, iteritems, with_metaclass, raise_from

from .. import _folders_schema_, _folders_defaults_
from ..utils import ListItem, build_url, localized_string


# ------------------------------------------------------------------------------
# cache
# ------------------------------------------------------------------------------

class Cache(dict):

    def __init__(self, items=None):
        if not items:
            items = []
        super(Cache, self).__init__({int(item.id): item for item in items})

    def __getitem__(self, key):
        return super(Cache, self).__getitem__(int(key))

    def __setitem__(self, key, value):
        return super(Cache, self).__setitem__(int(key), value)

    def __delitem__(self, key):
        return super(Cache, self).__delitem__(int(key))

    def update(self, items):
        return super(Cache, self).update({int(item.id): item for item in items})


# ------------------------------------------------------------------------------
# base types
# ------------------------------------------------------------------------------

def _date_(value):
    if isinstance(value, string_types):
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    return value

def _uuid_(value):
    if isinstance(value, string_types):
        return UUID(value)
    return value

def _json_(name, func):
    def getter(obj):
        return func(obj.__getattr__(name))
    return property(getter)


class MixerType(type):

    __json__ = {"__date__": _date_, "__uuid__": _uuid_}
    __attr_error__ = "'{}' object has no attribute '{{}}'"

    def __new__(cls, name, bases, namespace, **kwargs):
        namespace.setdefault("__slots__", set())
        namespace.setdefault("__attr_error__", cls.__attr_error__.format(name))
        for _name, _func in iteritems(namespace.pop("__json__", dict())):
            namespace[_name] = _json_(_name, _func)
        for _type, _func in iteritems(cls.__json__):
            for _name in namespace.pop(_type, set()):
                namespace[_name] = _json_(_name, _func)
        return type.__new__(cls, name, bases, namespace, **kwargs)


class MixerObject(with_metaclass(MixerType, object)):

    __slots__ = {"__data__"}

    def __new__(cls, data):
        if isinstance(data, dict):
            if not data:
                return None
            return super(MixerObject, cls).__new__(cls)
        return data

    def __init__(self, data):
        self.__data__ = data

    def __getitem__(self, name):
        return self.__data__[name]

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise_from(AttributeError(self.__attr_error__.format(name)), None)

    def __repr__(self):
        try:
            _repr_ = self._repr_
        except AttributeError:
            return super(MixerObject, self).__repr__()
        else:
            return _repr_.format(self)

    # XXX: not happy about plot() being here :(, but don't care enough to find
    # a better solution just right now
    def plot(self):
        return self._plot_.format(self)


class MixerItems(list):

    _ctor_ = MixerObject
    _content_ = "videos"
    _category_ = None

    def __init__(self, items, limit=0, content=None, category=None):
        super(MixerItems, self).__init__((self._ctor_(item) for item in items))
        self.more = (len(self) >= limit) if limit else False
        self.content = content or self._content_
        self.category = category or self._category_

    def items(self, *args):
        return (item.item(*args) for item in self if item)


# ------------------------------------------------------------------------------
# Mixer objects
# ------------------------------------------------------------------------------

# https://dev.mixer.com/rest/index.html#TimeStamped
class TimeStamped(MixerObject):

    __date__ = {"createdAt", "updatedAt", "deletedAt"}


# https://dev.mixer.com/rest/index.html#Resource
class Resource(MixerObject):

    _repr_ = "Resource({0.id}, url={0.url})"


_empty_thumbnail_ = Resource({"id": -1, "url": ""})


# folders ----------------------------------------------------------------------

class Folder(MixerObject):

    @property
    def style(self):
        try:
            return self["style"] or ""
        except KeyError:
            return ""

    def item(self, url):
        folder = _folders_schema_[self.type][self.style]
        label = localized_string(folder["id"])
        action = folder.get("action", self.type)
        plot = folder.get("plot", "")
        if isinstance(plot, int):
            plot = localized_string(plot)
        return ListItem(
            label, build_url(url, action=action), isFolder=True,
            infos={"video": {"title": label, "plot": plot}})


# games ------------------------------------------------------------------------

# https://dev.mixer.com/rest/index.html#GameTypeSimple
class GameTypeSimple(MixerObject):

    _repr_ = "Game({0.id}, name={0.name})"


# https://dev.mixer.com/rest/index.html#GameType
class GameType(GameTypeSimple):

    _plot_ = localized_string(30053)

    @property
    def description(self):
        try:
            return self["description"] or ""
        except KeyError:
            return ""

    @property
    def viewersCurrent(self):
        try:
            return self["viewersCurrent"]
        except KeyError:
            return 0

    @property
    def online(self):
        try:
            return self["online"]
        except KeyError:
            return 0

    def item(self, url, action):
        return ListItem(
            self.name, build_url(url, action=action, id=self.id), isFolder=True,
            infos={"video": {"plot": self.plot()}},
            fanart=self.backgroundUrl,
            poster=self.coverUrl)


_empty_game_ = GameType({"id": -1, "name": "", "backgroundUrl": "", "coverUrl": ""})


# users ------------------------------------------------------------------------

# https://dev.mixer.com/rest/index.html#SocialInfo
class SocialInfo(MixerObject): pass


# https://dev.mixer.com/rest/index.html#User
class User(TimeStamped):

    __json__ = {"social": SocialInfo}
    _repr_ = "User({0.id}, username={0.username})"


# channels ---------------------------------------------------------------------

# https://dev.mixer.com/rest/index.html#Channel
class Channel(TimeStamped):

    __uuid__ = {"costreamId"}
    _repr_ = "Channel({0.id}, token={0.token})"

# returned by https://mixer.com/api/v1/channels
class ExtendedChannel(Channel):

    __json__ = {"user": User}
    _audience_ = {"family": 30050, "teen": 30051, "18+": 30052}
    _plot_ = localized_string(30054)
    _online_plot_ = localized_string(30055)

    @property
    def thumbnail(self):
        return Resource(self["thumbnail"]) or _empty_thumbnail_

    @property
    def type(self):
        return GameType(self["type"]) or _empty_game_

    @property
    def audience(self):
        return localized_string(self._audience_.get(self["audience"], 30052))

    def plot(self):
        if self.online:
            return self._online_plot_.format(self)
        return super(ExtendedChannel, self).plot()

    def item(self, url, action):
        return ListItem(
            self.token, build_url(url, action=action, id=self.id), isFolder=True,
            infos={"video": {"plot": self.plot()}},
            fanart=self.bannerUrl,
            poster=self.user.avatarUrl)


# streams ----------------------------------------------------------------------

class Stream(ExtendedChannel):

    _repr_ = "Stream({0.id}, token={0.token})"
    _video_infos_ = {"mediatype": "video", "playcount": 0}

    def _item(self, path):
        if self.online:
            title = " - ".join((self.token, self.name))
            return ListItem(
                title, path,
                infos={"video": dict(self._video_infos_,
                                     title=title, plot=self.plot())},
                fanart=self.bannerUrl,
                thumb=self.thumbnail.url)

    def item(self, url, action):
        return self._item(build_url(url, action=action, id=self.id))


# vods -------------------------------------------------------------------------

class Locators(object):

    def __new__(cls, locators):
        if locators:
            return super(Locators, cls).__new__(cls, locators)
        return None

    def __init__(self, locators):
        for locator in locators:
            setattr(self, locator["locatorType"].lower(), locator["uri"])


class Vod(MixerObject):

    __json__ = {"contentLocators": Locators}
    __date__ = {"expirationDate", "uploadDate"}
    __uuid__ = {"contentId"}
    _repr_ = "Vod({0.id})"
    _video_infos_ = {"mediatype": "video"}
    _plot_ = localized_string(30057)

    @property
    def type(self):
        from .api import service
        try:
            game = service.game(self.typeId) if self.typeId else _empty_game_
        except Exception:
            sys.exc_clear()
        finally:
            return game

    @property
    def id(self):
        return self.shareableId

    def url(self, quality):
        locators = self.contentLocators
        if locators:
            if quality == 7: # inputstream.adaptive
                return getattr(locators, "ahls", None)
            return getattr(locators, "smoothstreaming", None)

    def _item(self, path):
        locators = self.contentLocators
        if locators:
            streamInfos = {"video": {"width": self.width,
                                     "height": self.height,
                                     "duration": self.durationInSeconds}}
            thumbnail_large = getattr(locators, "thumbnail_large", "")
            #thumbnail_small = getattr(locators, "thumbnail_small", "")
            return ListItem(
                self.title, path,
                infos={"video": dict(self._video_infos_,
                                     title=self.title, plot=self.plot())},
                streamInfos=streamInfos,
                fanart=thumbnail_large,
                thumb=thumbnail_large)

    def item(self, url, action):
        return self._item(build_url(url, action=action, id=self.id))


# ------------------------------------------------------------------------------
# lists, collections
# ------------------------------------------------------------------------------

class Folders(MixerItems):

    _ctor_ = Folder


class Home(Folders):

    def __init__(self, folders):
        super(Home, self).__init__(chain(folders, _folders_defaults_))


class Channels(MixerItems):

    _ctor_ = ExtendedChannel


class Games(MixerItems):

    _ctor_ = GameType


class Streams(MixerItems):

    _ctor_ = Stream


class TopStreams(Streams):

    def __init__(self, *args, **kwargs):
        super(TopStreams, self).__init__(*args, **kwargs)
        self.more = True


class Vods(MixerItems):

    _ctor_ = Vod

