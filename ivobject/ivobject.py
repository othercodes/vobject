from typing import Generator, List, Optional, Tuple

from .exceptions import *
import inspect
import sys

MIN_NUMBER_ARGS = 1
INVARIANT_NAME = 0
INVARIANT_METHOD = 1


class ImmutableDict(dict):
    def __hash__(self):
        return id(self)

    def __immutable(self, *args, **kwargs) -> None:
        raise CannotBeChangeException()

    __setitem__ = __immutable
    __delitem__ = __immutable
    clear = __immutable
    update = __immutable
    setdefault = __immutable
    pop = __immutable
    popitem = __immutable


class ArgsSpec(object):
    def __init__(self, method):
        try:
            if sys.version_info.major == 2:
                self.__argspec = inspect.getargspec(method)
                self.__varkw = self.__argspec.keywords
            else:
                self.__argspec = inspect.getfullargspec(method)
                self.__varkw = self.__argspec.varkw
        except TypeError:
            raise NotDeclaredArgsException()

    @property
    def args(self) -> List[str]:
        return self.__argspec.args

    @property
    def varargs(self) -> Optional[str]:
        return self.__argspec.varargs

    @property
    def keywords(self) -> Optional[str]:
        return self.__varkw

    @property
    def defaults(self) -> Optional[Tuple]:
        return self.__argspec.defaults


class ValueObject(object):
    def __new__(cls, *args, **kwargs):
        self = super(ValueObject, cls).__new__(cls)
        args_spec = ArgsSpec(self.__init__)

        def check_class_initialization() -> None:
            init_constructor_without_arguments = len(args_spec.args) <= MIN_NUMBER_ARGS

            if init_constructor_without_arguments:
                raise NotDeclaredArgsException()

            if None in args:
                raise ArgWithoutValueException('Missing value for {}'.format(
                    self.__class__.__name__
                ))

            if None in kwargs.values():
                raise ArgWithoutValueException('Missing value for {}'.format(
                    self.__class__.__name__
                ))

        def replace_mutable_kwargs_with_immutable_types() -> None:
            for arg, value in kwargs.items():
                if isinstance(value, dict):
                    kwargs[arg] = ImmutableDict(value)
                if isinstance(value, (list, set)):
                    kwargs[arg] = tuple(value)

        def assign_instance_arguments() -> None:
            defaults = () if not args_spec.defaults else args_spec.defaults
            self.__dict__.update(dict(zip(args_spec.args[:0:-1], defaults[::-1])))

            sanitized_args = []
            for arg in args:
                if isinstance(arg, dict):
                    sanitized_args.append(ImmutableDict(arg))
                elif isinstance(arg, (list, set)):
                    sanitized_args.append(tuple(arg))
                else:
                    sanitized_args.append(arg)

            self.__dict__.update(dict(list(zip(args_spec.args[1:], sanitized_args)) + list(kwargs.items())))

        def check_invariants() -> None:
            for invariant in obtain_invariants():
                if not invariant_execute(invariant[INVARIANT_METHOD]):
                    raise ViolatedInvariantException('Value in {} violates "{}" invariant rule'.format(
                        self.__class__.__name__,
                        invariant[INVARIANT_NAME].replace('_', ' ')
                    ))

        def invariant_execute(invariant) -> bool:
            return_value = invariant(self, self)

            if not isinstance(return_value, bool):
                raise InvariantReturnValueException()

            return return_value

        def is_invariant_method_with_name(method: str, name: str) -> bool:
            try:
                return name in str(method) and '__init__' not in str(method)
            except TypeError:
                return False

        def is_invariant(method: str) -> bool:
            return is_invariant_method_with_name(method, 'invariant_fn')

        def is_param_invariant(method: str) -> bool:
            return is_invariant_method_with_name(method, 'param_invariant_fn')

        def obtain_invariants() -> Generator:
            param_invariants = [(member[INVARIANT_NAME], member[INVARIANT_METHOD]) for member in
                                inspect.getmembers(cls, is_param_invariant)]
            invariants = [(member[INVARIANT_NAME], member[INVARIANT_METHOD]) for member in
                          inspect.getmembers(cls, is_invariant)]
            for invariant in param_invariants + invariants:
                yield invariant

        check_class_initialization()
        replace_mutable_kwargs_with_immutable_types()
        assign_instance_arguments()
        check_invariants()

        return self

    def __setattr__(self, name, value) -> None:
        raise CannotBeChangeException()

    def __eq__(self, other) -> bool:
        if other is None:
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other) -> bool:
        return self.__dict__ != other.__dict__

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        args_spec = ArgsSpec(self.__init__)
        args_values = ["{}={}".format(arg, getattr(self, arg)) for arg in args_spec.args[1:]]

        return "{}({})".format(self.__class__.__name__, ", ".join(args_values))

    def __hash__(self) -> int:
        return self.hash

    @property
    def hash(self) -> int:
        return hash(repr(self))
