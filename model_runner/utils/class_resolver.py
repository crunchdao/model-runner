import importlib
import inspect
import logging
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

    logger.info(f"Finding classes extending '{base_class_name}' in '{code_path}'.")
    # todo: maybe is not required to walk packages and only import the root module ?
    base_class = resolve_class(base_class_name)

    base_package, _, _ = base_class_name.partition(".")
    skip_if_module_prefix = f"{base_package}."

    for importer, module_name, is_package in pkgutil.walk_packages([code_path]):
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error importing module '{module_name}'", exc_info=True)
            continue

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate is base_class:
                logger.debug(f"Skipping {candidate} due to being the primary class.")
                continue

            candidate_module_name = getattr(candidate, "__module__", "")
            if candidate_module_name == base_package or candidate_module_name.startswith(skip_if_module_prefix):
                logger.debug(f"Skipping {candidate} due to being in {base_package}.")
                continue

            if not issubclass(candidate, (base_class)):
                logger.debug(f"Class {candidate} does not inherit from {base_class}.")
                continue

            logger.info(f"Found class {candidate} that inherits from {base_class}.")
            return candidate(*args, **kwargs)

    raise ImportError(f"No Inherited class found from {base_class}.")


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
