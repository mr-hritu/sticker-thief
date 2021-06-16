import warnings
from copy import copy
from typing import cast, Dict

from telegram import Bot
from telegram.ext import PicklePersistence


class PicklePersistenceWorkaround(PicklePersistence):
    def _insert_bot(self, obj: object, memo: Dict[int, object]) -> object:  # pylint: disable=R0911
        obj_id = id(obj)
        if obj_id in memo:
            return memo[obj_id]

        if isinstance(obj, Bot):
            memo[obj_id] = self.bot
            return self.bot
        if isinstance(obj, str) and obj == self.REPLACED_BOT:
            memo[obj_id] = self.bot
            return self.bot
        if isinstance(obj, (list, set)):
            # We copy the iterable here for thread safety, i.e. make sure the object we iterate
            # over doesn't change its length during the iteration
            temp_iterable = obj.copy()
            new_iterable = obj.__class__(self._insert_bot(item, memo) for item in temp_iterable)
            memo[obj_id] = new_iterable
            return new_iterable
        if isinstance(obj, (tuple, frozenset)):
            # tuples and frozensets are immutable so we don't need to worry about thread safety
            new_immutable = obj.__class__(self._insert_bot(item, memo) for item in obj)
            memo[obj_id] = new_immutable
            return new_immutable
        if isinstance(obj, type):
            # classes usually do have a __dict__, but it's not writable
            warnings.warn(
                'BasePersistence.insert_bot does not handle classes. See '
                'the docs of BasePersistence.insert_bot for more information.',
                RuntimeWarning,
            )
            return obj

        try:
            new_obj = copy(obj)
        except Exception:
            warnings.warn(
                'BasePersistence.insert_bot does not handle objects that can not be copied. See '
                'the docs of BasePersistence.insert_bot for more information.',
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
                new_obj[self._insert_bot(k, memo)] = self._insert_bot(val, memo)
            memo[obj_id] = new_obj
            return new_obj
        if hasattr(obj, '__dict__'):
            for attr_name, attr in new_obj.__dict__.items():
                try:
                    setattr(new_obj, attr_name, self._insert_bot(attr, memo))
                except Exception as e:
                    print(f"\tcatched exception: {str(e)}")
                    return obj

            memo[obj_id] = new_obj
            return new_obj
        if hasattr(obj, '__slots__'):
            for attr_name in obj.__slots__:
                setattr(
                    new_obj,
                    attr_name,
                    self._insert_bot(self._insert_bot(getattr(new_obj, attr_name), memo), memo),
                )
            memo[obj_id] = new_obj
            return new_obj

        return obj
