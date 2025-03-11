import logging

import importlib
import inspect
import pkgutil

logger = logging.getLogger(f'model_runner.{__name__}')

def load_instance(code_path: str, base_class_name: str, *args, **kwargs):
    """
    Dynamically searches for and instantiates a class by its name, assuming it inherits from a base class.
    :param code_path: The path to the directory containing the code.
    :param base_class_name: The full name of the base class.
    :param args: Positional arguments to pass to the class constructor.
    :param kwargs: Keyword arguments to pass to the class constructor.
    :return: An instance of the class if successfully found and instantiated.
    :raises ImportError: If the class cannot be found or does not inherit from the base class.
    """
    import sys
    sys.path.append(code_path)

    logger.info(f"Loading class '{base_class_name}' from '{code_path}'")
    # todo: maybe is not required to walk packages and only import the root module ?
    base_class = resolve_class(base_class_name)
    for importer, module_name, is_package in pkgutil.walk_packages([code_path]):
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error importing module '{module_name}'", exc_info=True)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, (base_class)) and obj is not base_class:
                logger.info(f"Found class '{obj.__name__}' that inherits from '{base_class.__name__}'.")
                return obj(*args, **kwargs)
            else:
                logger.debug(f"Class '{obj.__name__}' does not inherit from '{base_class.__name__}'.")

    raise ImportError(f"No Inherited class found from '{base_class}'.")


def resolve_class(class_full_name: str):
    module_name, _, class_name = class_full_name.rpartition('.')
    if not module_name:
        raise ValueError(f"Invalid class name '{class_name}'. Use 'module.ClassName' format.")
    module = importlib.import_module(module_name)
    if not hasattr(module, class_name):
        raise ValueError(f"Class '{class_name}' not found in module '{module_name}'.")
    class_obj = getattr(module, class_name)
    if not inspect.isclass(class_obj):
        raise ValueError(f"Object '{class_name}' in module '{module_name}' is not a class.")

    return class_obj
