#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script prepares the file(s) saved by PicklePersistence for v13.1. How you do it:

1. Edit the PicklePersistence according to your settings below.
2. Run this script *before* upgrading from 12.x to v13.1
3. Upgrade to v13.1 and run your bot to make sure everything is working

WARNING: Save a backup of your pickle file(s) before running this!
"""
import warnings
from copy import copy
from typing import cast, Dict, Any

from telegram import Bot
from telegram.ext import PicklePersistence

from bot.pickle_persistence_workaround import PicklePersistenceWorkaround

"""
Instantiate your persistence with the same parameters as in your bot script!
"""
persistence = PicklePersistenceWorkaround('persistence\data.pickle')


# Don't touch anything below this line!
# -------------------------------------------------------------------------------------------------
def replace_bot(obj: object, memo: Dict[int, Any]) -> object:  # pylint: disable=R0911
    obj_id = id(obj)
    if obj_id in memo:
        return memo[obj_id]

    if isinstance(obj, Bot):
        memo[obj_id] = 'bot_instance_replaced_by_ptb_persistence'
        return 'bot_instance_replaced_by_ptb_persistence'
    if isinstance(obj, (list, set)):
        # We copy the iterable here for thread safety, i.e. make sure the object we iterate
        # over doesn't change its length during the iteration
        temp_iterable = obj.copy()
        new_iterable = obj.__class__(replace_bot(item, memo) for item in temp_iterable)
        memo[obj_id] = new_iterable
        return new_iterable
    if isinstance(obj, (tuple, frozenset)):
        # tuples and frozensets are immutable so we don't need to worry about thread safety
        new_immutable = obj.__class__(replace_bot(item, memo) for item in obj)
        memo[obj_id] = new_immutable
        return new_immutable

    try:
        new_obj = copy(obj)
        memo[obj_id] = new_obj
    except Exception:
        warnings.warn(
            'BasePersistence.replace_bot does not handle objects that can not be copied. See '
            'the docs of BasePersistence.replace_bot for more information.',
            RuntimeWarning,
        )
        memo[obj_id] = obj
        return obj

    if isinstance(obj, dict):
        # We handle dicts via copy(obj) so we don't have to make a
        # difference between dict and defaultdict
        new_obj = cast(dict, new_obj)
        # We can't iterate over obj.items() due to thread safety, i.e. the dicts length may
        # change during the iteration
        temp_dict = new_obj.copy()
        new_obj.clear()
        for k, val in temp_dict.items():
            new_obj[replace_bot(k, memo)] = replace_bot(val, memo)
        memo[obj_id] = new_obj
        return new_obj
    if hasattr(obj, '__dict__'):
        for attr_name, attr in new_obj.__dict__.items():
            # if isinstance(new_obj, UUID):
            #     print("skipping UUID instance")
            #     continue
            try:
                setattr(new_obj, attr_name, replace_bot(attr, memo))
            except Exception as e:
                print(f"\tcatched exception: {str(e)}")
                return obj

        memo[obj_id] = new_obj
        return new_obj
    if hasattr(obj, '__slots__'):
        for attr_name in new_obj.__slots__:
            setattr(
                new_obj,
                attr_name,
                replace_bot(replace_bot(getattr(new_obj, attr_name), memo), memo),
            )
        memo[obj_id] = new_obj
        return new_obj

    return obj


print('Loading data.')
persistence.get_user_data()
persistence.get_chat_data()
persistence.get_bot_data()
print('Done.')

print('Converting data.')
persistence.bot_data = replace_bot(persistence.bot_data, {})
persistence.chat_data = replace_bot(persistence.chat_data, {})
persistence.user_data = replace_bot(persistence.user_data, {})
print('Done.')

print('Writing to file.')
persistence.flush()
print('Done. Upgrade to v13.1 now and run your bot to make sure everything works.')
