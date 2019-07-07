import re
import time

from nxtools import *

from .common import *
from .constants import *


def shorten(instr, nlen):
    line = instr.split("\n")[0]
    if len(line) < 100:
        return line
    return line[:nlen] + "..."


def filter_match(f, r):
    """OR"""
    if type(f) == list:
        res = False
        for fl in f:
            if re.match(fl, r):
                return True
        return False
    else:
        return re.match(f, r)

def tree_indent(data):
    has_children = False
    for i, row in enumerate(data):
        value = row["value"]
        depth = len(value.split("."))
        parentindex = None
        for j in range(i - 1, -1, -1):
            if value.startswith(data[j]["value"] + "."):
                parentindex = j
                data[j]["has_children"] = True
                break
        if parentindex is None:
            data[i]["indent"] = 0
            continue
        has_children = True
        data[i]["indent"] = data[parentindex]["indent"] + 1

    for i, row in enumerate(data):
        role = row.get("role", "option")
        if role in ["label", "hidden"]:
            continue
        elif has_children and row.get("has_children"):#row["indent"] == 0:
            data[i]["role"] = "header"
        else:
            data[i]["role"] = "option"

#
# CS Caching
#

FMH_DATA = {} # id_folder-->key
def folder_metaset_helper(id_folder, key):
    if id_folder not in FMH_DATA:
        d = {}
        for fkey, settings in config["folders"].get(id_folder, {}).get("meta_set", []):
            d[fkey] = settings or {}
        FMH_DATA[id_folder] = d
    return FMH_DATA.get(id_folder, {}).get(key, {})


CSH_DATA = {} # key --> id_folder
def csdata_helper(meta_type, id_folder):
    key = meta_type.key
    if key not in CSH_DATA:
        CSH_DATA[key] = {
                0 : config["cs"].get(meta_type["cs"], [])
            }
    if id_folder not in CSH_DATA[key]:
        folder_settings = folder_metaset_helper(id_folder, meta_type.key)
        folder_cs = folder_settings.get("cs", meta_type.get("cs", "urn:special:nonexistent-cs"))
        folder_filter = folder_settings.get("filter")
        fdata = config["cs"].get(folder_cs, [])
        if folder_filter:
            CSH_DATA[key][id_folder] = [r for r in fdata if filter_match(folder_filter, r[0])]
        else:
            CSH_DATA[key][id_folder] = fdata
    return CSH_DATA[key].get(id_folder, False) or CSH_DATA[key][0]


CSA_DATA = {}
def csa_helper(meta_type, id_folder, value, lang):
    key = meta_type.key
    if not key in CSA_DATA:
        CSA_DATA[key] = {}
    if not id_folder in CSA_DATA[key]:
        CSA_DATA[key][id_folder] = {}
    if not value in CSA_DATA[key][id_folder]:
        for csval, settings in csdata_helper(meta_type, id_folder):
            if csval == value:
                settings = settings or {}
                CSA_DATA[key][id_folder][value] = settings.get("aliases", {})
                break
        else:
            for csval, settings in csdata_helper(meta_type, 0):
                if csval == value:
                    settings = settings or {}
                    CSA_DATA[key][id_folder][value] = settings.get("aliases", {})
                    break
            else:
                CSA_DATA[key][id_folder][value] = {}
    return CSA_DATA[key][id_folder][value].get(lang) or CSA_DATA[key][id_folder][value].get("en", value)# "!{}".format(CSA_DATA[key][id_folder][value]) )


CSD_DATA = {}
def csd_helper(meta_type, id_folder, value, lang):
    key = meta_type.key
    if not key in CSD_DATA:
        CSD_DATA[key] = {}
    if not id_folder in CSD_DATA[key]:
        CSD_DATA[key][id_folder] = {}
    if not value in CSD_DATA[key][id_folder]:
        for csval, settings in csdata_helper(meta_type, id_folder):
            if csval == value:
                CSD_DATA[key][id_folder][value] = settings.get("description", {})
                break
        else:
            for csval, settings in csdata_helper(meta_type, 0):
                if csval == value:
                    CSD_DATA[key][id_folder][value] = settings.get("description", {})
                    break
            else:
                CSD_DATA[key][id_folder][value] = {}
    return CSD_DATA[key][id_folder][value].get(lang) or CSD_DATA[key][id_folder][value].get("en", value)

#
# Formating helpers
#

def format_text(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    if result == "brief":
        return {"value" : shorten(value, 100)}
    if result == "full":
        return {"value" : value}
    if kwargs.get("shorten"): #TODO: deprecated. remove
        return shorten(value, kwargs["shorten"])
    return value


def format_integer(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    value = int(value)

    if not value and meta_type.settings.get("hide_null", False):
        alias = ""

    if meta_type.key == "file/size":
        alias = format_filesize(value)

    elif meta_type.key == "status":
        alias = get_object_state_name(value).upper()

    elif meta_type.key == "content_type":
        alias = get_content_type_name(value).upper()

    elif meta_type.key == "media_type":
        alias = get_media_type_name(value).upper()

    elif meta_type.key == "id_storage":
        alias = storages[value].__repr__().lstrip("storage ")

    else:
        alias = str(value)

    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_numeric(meta_type, value, **kwargs):
    if type(value) not in [int, float]:
        try:
            value = float(value)
        except ValueError:
            value = 0
    result = kwargs.get("result", "alias")
    alias = "{:.03f}".format(value)
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_boolean(meta_type, value, **kwargs):
    value = int(value)
    result = kwargs.get("result", "alias")
    alias = ["no", "yes"][bool(value)]
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_datetime(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    time_format = meta_type.settings.get("format", False) or kwargs.get("format", "%Y-%m-%d %H:%M")
    alias = format_time(value, time_format, never_placeholder=kwargs.get("never_placeholder", "never"))
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_timecode(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    alias = s2time(value)
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_regions(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    alias = "{} regions".format(len(value))
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_fract(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    alias = value #TODO
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias


def format_select(meta_type, value, **kwargs):
    value = str(value)
    lang = kwargs.get("language", config.get("language", "en"))
    result = kwargs.get("result", "alias")

    try:
        id_folder = kwargs.get("id_folder") or kwargs["parent"].meta["id_folder"]
    except KeyError:
        id_folder = 0

    if result == "brief":
        return {
                "value" : value,
                "alias" : csa_helper(meta_type, id_folder, value, lang)
            }

    elif result == "full":
        result = []
        has_zero = has_selected = False
        for csval, settings in csdata_helper(meta_type, id_folder):
            settings = settings or {}
            if csval == "0":
                has_zero = True
            if value == csval:
                has_selected = True
            aliases = {"en" : csval}
            aliases.update(settings.get("aliases", {}))
            description = {"en" : ""}
            description.update(settings.get("description", {}))
            role = settings.get("role", "option")
            if role == "hidden":
                continue
            result.append({
                    "value" : csval,
                    "alias" : aliases.get(lang, aliases["en"]),
                    "description" : description.get(lang, description["en"]),
                    "selected" : value == csval,
                    "role" : role,
                    "indent" : 0
                })
        result.sort(key=lambda x: str(x["value"]))
        if not has_selected:
            if has_zero:
                result[0]["selected"] = True
            else:
                result.insert(0, {"value" : "", "alias" : "", "selected": True, "role" : "option"})
        if meta_type.get("mode") == "tree":
            sort_mode = lambda x: "".join([n.zfill(3) for n in x["value"].split(".")])
            result.sort(key=sort_mode)
            tree_indent(result)
        else:
            if meta_type.get("order") == "alias":
                sort_mode = lambda x: str(x["alias"])
            else:
                sort_mode = lambda x: str(x["value"])
            result.sort(key=sort_mode)
        return result

    elif result == "description":
        return csd_helper(meta_type, id_folder, value, lang)

    else: # alias
        return csa_helper(meta_type, id_folder, value, lang)


def format_list(meta_type, value, **kwargs):
    if type(value) == str:
        value = [value]
    elif type(value) != list:
        logging.warning("Unknown value {} for key {}".format(value, meta_type))
        value = []

    value = [str(v) for v in value]
    lang = kwargs.get("language", config.get("language", "en"))
    result = kwargs.get("result", "alias")

    try:
        id_folder = kwargs.get("id_folder") or kwargs["parent"].meta["id_folder"]
    except KeyError:
        id_folder = 0

    if result == "brief":
        return {
                "value" : value,
                "alias" : ", ".join([csa_helper(meta_type, id_folder, v, lang) for v in value])
        }

    elif result == "full":
        result = []
        for csval, settings in csdata_helper(meta_type, id_folder):
            settings = settings or {}
            aliases = {"en" : csval}
            aliases.update(settings.get("aliases", {}))
            description = {"en" : ""}
            description.update(settings.get("description", {}))
            role = settings.get("role", "option")
            if role == "hidden":
                continue
            result.append({
                    "value" : csval,
                    "alias" : aliases.get(lang, aliases["en"]),
                    "description" : description.get(lang, description["en"]),
                    "selected" : csval in value,
                    "role" : role,
                    "indent" : 0
                })
        if meta_type.get("mode") == "tree":
            sort_mode = lambda x: "".join([n.zfill(3) for n in x["value"].split(".")])
            result.sort(key=sort_mode)
            tree_indent(result)
        else:
            if meta_type.get("order") == "alias":
                sort_mode = lambda x: str(x["alias"])
            else:
                sort_mode = lambda x: str(x["value"])
            result.sort(key=sort_mode)
        return result

    elif result == "description":
        if len(value):
            return csd_helper(meta_type, id_folder, value[0], lang)
        return ""

    else: # alias
        return ", ".join([csa_helper(meta_type, id_folder, v, lang) for v in value])


def format_color(meta_type, value, **kwargs):
    result = kwargs.get("result", "alias")
    alias = "#{0:06X}".format(value)
    if result in ["brief", "full"]:
        return {
                "value" : value,
                "alias" : alias
            }
    return alias



humanizers = {
        -1       : None,
        STRING   : format_text,
        TEXT     : format_text,
        INTEGER  : format_integer,
        NUMERIC  : format_numeric,
        BOOLEAN  : format_boolean,
        DATETIME : format_datetime,
        TIMECODE : format_timecode,
        REGIONS  : format_regions,
        FRACTION : format_fract,
        SELECT   : format_select,
        LIST     : format_list,
        COLOR    : format_color
    }
