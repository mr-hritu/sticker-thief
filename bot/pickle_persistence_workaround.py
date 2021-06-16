import warnings
from copy import copy
from typing import cast, Dict

from telegram import Bot
from telegram.ext import PicklePersistence


class PicklePersistenceWorkaround(PicklePersistence):
    def insert_bot(self, obj: object) -> object:
        """
        Replaces all instances of :attr:`REPLACED_BOT` that occur within the passed object with
        :attr:`bot`. Currently, this handles objects of type ``list``, ``tuple``, ``set``,
        ``frozenset``, ``dict``, ``defaultdict`` and objects that have a ``__dict__`` or
        ``__slots__`` attribute, excluding classes and objects that can't be copied with
        ``copy.copy``, or that don't allow to change their attributes with ``__setattr__``.

        Args:
            obj (:obj:`object`): The object

        Returns:
            :obj:`obj`: Copy of the object with Bot instances inserted.
        """
        return self._insert_bot(obj, {})

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
        try:
            if hasattr(obj, '__dict__'):
                for attr_name, attr in new_obj.__dict__.items():
                    setattr(new_obj, attr_name, self._insert_bot(attr, memo))

                memo[obj_id] = new_obj
                return new_obj
        except Exception:
            warnings.warn(
                'BasePersistence.insert_bot does not handle objects that don\'t allow to change their attributes '
                'with setattr(). See the docs of BasePersistence.insert_bot for more information.',
                RuntimeWarning,
            )
            memo[obj_id] = obj
            return obj
        try:
            if hasattr(obj, '__slots__'):
                for attr_name in obj.__slots__:
                    setattr(
                        new_obj,
                        attr_name,
                        self._insert_bot(self._insert_bot(getattr(new_obj, attr_name), memo), memo),
                    )
                memo[obj_id] = new_obj
                return new_obj
        except Exception:
            warnings.warn(
                'BasePersistence.insert_bot does not handle objects that don\'t allow to change their attributes '
                'with setattr(). See the docs of BasePersistence.insert_bot for more information.',
                RuntimeWarning,
            )
            memo[obj_id] = obj
            return obj

        return obj

    @classmethod
    def replace_bot(cls, obj: object) -> object:
        """
        Replaces all instances of :class:`telegram.Bot` that occur within the passed object with
        :attr:`REPLACED_BOT`. Currently, this handles objects of type ``list``, ``tuple``, ``set``,
        ``frozenset``, ``dict``, ``defaultdict`` and objects that have a ``__dict__`` or
        ``__slots__`` attribute, excluding classes and objects that can't be copied with
        ``copy.copy``, or that don't allow to change their attributes with ``__setattr__``.

        Args:
            obj (:obj:`object`): The object

        Returns:
            :obj:`obj`: Copy of the object with Bot instances replaced.
        """
        return cls._replace_bot(obj, {})

    @classmethod
    def _replace_bot(cls, obj: object, memo: Dict[int, object]) -> object:  # pylint: disable=R0911
        obj_id = id(obj)
        if obj_id in memo:
            return memo[obj_id]

        if isinstance(obj, Bot):
            memo[obj_id] = cls.REPLACED_BOT
            return cls.REPLACED_BOT
        if isinstance(obj, (list, set)):
            # We copy the iterable here for thread safety, i.e. make sure the object we iterate
            # over doesn't change its length during the iteration
            temp_iterable = obj.copy()
            new_iterable = obj.__class__(cls._replace_bot(item, memo) for item in temp_iterable)
            memo[obj_id] = new_iterable
            return new_iterable
        if isinstance(obj, (tuple, frozenset)):
            # tuples and frozensets are immutable so we don't need to worry about thread safety
            new_immutable = obj.__class__(cls._replace_bot(item, memo) for item in obj)
            memo[obj_id] = new_immutable
            return new_immutable
        if isinstance(obj, type):
            # classes usually do have a __dict__, but it's not writable
            warnings.warn(
                'BasePersistence.replace_bot does not handle classes. See '
                'the docs of BasePersistence.replace_bot for more information.',
                RuntimeWarning,
            )
            return obj

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
                new_obj[cls._replace_bot(k, memo)] = cls._replace_bot(val, memo)
            memo[obj_id] = new_obj
            return new_obj
        try:
            if hasattr(obj, '__dict__'):
                for attr_name, attr in new_obj.__dict__.items():
                    setattr(new_obj, attr_name, cls._replace_bot(attr, memo))

                memo[obj_id] = new_obj
                return new_obj
        except Exception:
            warnings.warn(
                'BasePersistence.insert_bot does not handle objects that don\'t allow to change their attributes '
                'with setattr(). See the docs of BasePersistence.replace_bot for more information.',
                RuntimeWarning,
            )
            memo[obj_id] = obj
            return obj
        try:
            if hasattr(obj, '__slots__'):
                for attr_name in new_obj.__slots__:
                    setattr(
                        new_obj,
                        attr_name,
                        cls._replace_bot(cls._replace_bot(getattr(new_obj, attr_name), memo), memo),
                    )
                memo[obj_id] = new_obj
                return new_obj
        except Exception:
            warnings.warn(
                'BasePersistence.insert_bot does not handle objects that don\'t allow to change their attributes '
                'with setattr(). See the docs of BasePersistence.replace_bot for more information.',
                RuntimeWarning,
            )
            memo[obj_id] = obj
            return obj

        return obj
