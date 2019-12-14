# -*- coding: utf-8 -*-


from __future__ import absolute_import, division, unicode_literals


_folders_schema_ = {
    "carousel": {
        "": {
            "id": 30007,
            "plot": 30008,
            "action": "featured"
        }
    },
    "games": {
        "": {
            "id": 30011,
            "plot": 30012,
            "action": "top_games"
        },
        "browse": {
            "id": 30006,
            "action": "browse_games"
        },
        "search": {
            "id": 30006,
            "action": "search_games"
        }
    },
    "channels": {
        "onlyOnMixer": {
            "id": 30009,
            "plot": 30010,
            "action": "spotlight"
        },
        "upAndComing": {
            "id": 30013,
            "plot": 30014,
            "action": "up_and_coming"
        },
        "topStreams": {
            "id": 30015,
            "action": "top_streams"
        },
        "browse": {
            "id": 30003,
            "action": "browse_channels"
        },
        "search": {
            "id": 30003,
            "action": "search_channels"
        }
    },
    "browse": {
        "": {
            "id": 30001
        }
    },
    "search": {
        "": {
            "id": 30002
        }
    }
}


_folders_defaults_ = (
    {"type": "channels", "style": "topStreams"},
    {"type": "browse"},
    {"type": "search"}
)


_subfolders_defaults_ = ("channels", "games")

