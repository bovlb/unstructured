import functools
import importlib
import json
import logging
import os
import platform
import subprocess
from datetime import datetime
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import magic
import matplotlib.pyplot as plt
import requests
from matplotlib import colors, patches
from pdf2image import convert_from_path
from PIL import Image
from typing_extensions import ParamSpec

from unstructured.__version__ import __version__

DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d+%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z")
TYPE_TO_COLOUR_MAP = {
    "Text": "blue",
    "FigureCaption": "orange",
    "NarrativeText": "green",
    "Title": "red",
    "Address": "purple",
    "EmailAddress": "brown",
    "Image": "pink",
    "PageBreak": "gray",
    "Table": "olive",
    "Header": "cyan",
    "Footer": "coral",
    "Formula": "gold",
    "ListItem": "skyblue",
    "UncategorizedText": "slateblue",
}

_T = TypeVar("_T")
_P = ParamSpec("_P")


class lazyproperty(Generic[_T]):
    """Decorator like @property, but evaluated only on first access.

    Like @property, this can only be used to decorate methods having only a `self` parameter, and
    is accessed like an attribute on an instance, i.e. trailing parentheses are not used. Unlike
    @property, the decorated method is only evaluated on first access; the resulting value is
    cached and that same value returned on second and later access without re-evaluation of the
    method.

    Like @property, this class produces a *data descriptor* object, which is stored in the __dict__
    of the *class* under the name of the decorated method ('fget' nominally). The cached value is
    stored in the __dict__ of the *instance* under that same name.

    Because it is a data descriptor (as opposed to a *non-data descriptor*), its `__get__()` method
    is executed on each access of the decorated attribute; the __dict__ item of the same name is
    "shadowed" by the descriptor.

    While this may represent a performance improvement over a property, its greater benefit may be
    its other characteristics. One common use is to construct collaborator objects, removing that
    "real work" from the constructor, while still only executing once. It also de-couples client
    code from any sequencing considerations; if it's accessed from more than one location, it's
    assured it will be ready whenever needed.

    Loosely based on: https://stackoverflow.com/a/6849299/1902513.

    A lazyproperty is read-only. There is no counterpart to the optional "setter" (or deleter)
    behavior of an @property. This is critically important to maintaining its immutability and
    idempotence guarantees. Attempting to assign to a lazyproperty raises AttributeError
    unconditionally.

    The parameter names in the methods below correspond to this usage example::

        class Obj(object)

            @lazyproperty
            def fget(self):
                return 'some result'

        obj = Obj()

    Not suitable for wrapping a function (as opposed to a method) because it is not callable.
    """

    def __init__(self, fget: Callable[..., _T]) -> None:
        """*fget* is the decorated method (a "getter" function).

        A lazyproperty is read-only, so there is only an *fget* function (a regular
        @property can also have an fset and fdel function). This name was chosen for
        consistency with Python's `property` class which uses this name for the
        corresponding parameter.
        """
        # --- maintain a reference to the wrapped getter method
        self._fget = fget
        # --- and store the name of that decorated method
        self._name = fget.__name__
        # --- adopt fget's __name__, __doc__, and other attributes
        functools.update_wrapper(self, fget)  # pyright: ignore

    def __get__(self, obj: Any, type: Any = None) -> _T:
        """Called on each access of 'fget' attribute on class or instance.

        *self* is this instance of a lazyproperty descriptor "wrapping" the property
        method it decorates (`fget`, nominally).

        *obj* is the "host" object instance when the attribute is accessed from an
        object instance, e.g. `obj = Obj(); obj.fget`. *obj* is None when accessed on
        the class, e.g. `Obj.fget`.

        *type* is the class hosting the decorated getter method (`fget`) on both class
        and instance attribute access.
        """
        # --- when accessed on class, e.g. Obj.fget, just return this descriptor
        # --- instance (patched above to look like fget).
        if obj is None:
            return self  # type: ignore

        # --- when accessed on instance, start by checking instance __dict__ for
        # --- item with key matching the wrapped function's name
        value = obj.__dict__.get(self._name)
        if value is None:
            # --- on first access, the __dict__ item will be absent. Evaluate fget()
            # --- and store that value in the (otherwise unused) host-object
            # --- __dict__ value of same name ('fget' nominally)
            value = self._fget(obj)
            obj.__dict__[self._name] = value
        return cast(_T, value)

    def __set__(self, obj: Any, value: Any) -> None:
        """Raises unconditionally, to preserve read-only behavior.

        This decorator is intended to implement immutable (and idempotent) object
        attributes. For that reason, assignment to this property must be explicitly
        prevented.

        If this __set__ method was not present, this descriptor would become a
        *non-data descriptor*. That would be nice because the cached value would be
        accessed directly once set (__dict__ attrs have precedence over non-data
        descriptors on instance attribute lookup). The problem is, there would be
        nothing to stop assignment to the cached value, which would overwrite the result
        of `fget()` and break both the immutability and idempotence guarantees of this
        decorator.

        The performance with this __set__() method in place was roughly 0.4 usec per
        access when measured on a 2.8GHz development machine; so quite snappy and
        probably not a rich target for optimization efforts.
        """
        raise AttributeError("can't set attribute")


def save_as_jsonl(data: List[Dict], filename: str) -> None:
    with open(filename, "w+") as output_file:
        output_file.writelines(json.dumps(datum) + "\n" for datum in data)


def read_from_jsonl(filename: str) -> List[Dict]:
    with open(filename) as input_file:
        return [json.loads(line) for line in input_file]


def requires_dependencies(
    dependencies: Union[str, List[str]],
    extras: Optional[str] = None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    if isinstance(dependencies, str):
        dependencies = [dependencies]

    def decorator(func: Callable[_P, _T]) -> Callable[_P, _T]:
        @wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs):
            missing_deps: List[str] = []
            for dep in dependencies:
                if not dependency_exists(dep):
                    missing_deps.append(dep)
            if len(missing_deps) > 0:
                raise ImportError(
                    f"Following dependencies are missing: {', '.join(missing_deps)}. "
                    + (
                        f"""Please install them using `pip install "unstructured[{extras}]"`."""
                        if extras
                        else f"Please install them using `pip install {' '.join(missing_deps)}`."
                    ),
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def dependency_exists(dependency: str):
    try:
        importlib.import_module(dependency)
    except ImportError as e:
        # Check to make sure this isn't some unrelated import error.
        if dependency in repr(e):
            return False
    return True


# Copied from unstructured/ingest/connector/biomed.py
def validate_date_args(date: Optional[str] = None):
    if not date:
        raise ValueError("The argument date is None.")

    for format in DATE_FORMATS:
        try:
            datetime.strptime(date, format)
            return True
        except ValueError:
            pass

    raise ValueError(
        f"The argument {date} does not satisfy the format: "
        "YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD+HH:MM:SS or YYYY-MM-DDTHH:MM:SStz",
    )


def _first_and_remaining_iterator(it: Iterable) -> Tuple[Any, Iterator]:
    iterator = iter(it)
    try:
        out = next(iterator)
    except StopIteration:
        raise ValueError(
            "Expected at least 1 element in iterable from which to retrieve first, got empty "
            "iterable.",
        )
    return out, iterator


def first(it: Iterable) -> Any:
    """Returns the first item from an iterable. Raises an error if the iterable is empty."""
    out, _ = _first_and_remaining_iterator(it)
    return out


def only(it: Iterable) -> Any:
    """Returns the only element from a singleton iterable. Raises an error if the iterable is not a
    singleton."""
    out, iterator = _first_and_remaining_iterator(it)
    if any(True for _ in iterator):
        raise ValueError(
            "Expected only 1 element in passed argument, instead there are at least 2 elements.",
        )
    return out


def scarf_analytics():
    try:
        subprocess.check_output("nvidia-smi")
        gpu_present = True
    except Exception:
        gpu_present = False
        pass

    python_version = ".".join(platform.python_version().split(".")[:2])

    try:
        if os.getenv("SCARF_NO_ANALYTICS") != "true" and os.getenv("DO_NOT_TRACK") != "true":
            if "dev" in __version__:
                requests.get(
                    "https://packages.unstructured.io/python-telemetry?version="
                    + __version__
                    + "&platform="
                    + platform.system()
                    + "&python"
                    + python_version
                    + "&arch="
                    + platform.machine()
                    + "&gpu="
                    + str(gpu_present)
                    + "&dev=true",
                )
            else:
                requests.get(
                    "https://packages.unstructured.io/python-telemetry?version="
                    + __version__
                    + "&platform="
                    + platform.system()
                    + "&python"
                    + python_version
                    + "&arch="
                    + platform.machine()
                    + "&gpu="
                    + str(gpu_present)
                    + "&dev=false",
                )
    except Exception:
        pass


def draw_bboxes_on_pdf_or_image(
    file_path,
    elements,
    desired_width=20,
    save_images=False,
    save_coordinates=False,
    output_folder=None,
    plot=False,
):
    """draw superimposed bounding boxes in pdf|images per page for the document in file_path"""

    mimetype = magic.from_file(file_path)
    if "PDF" in mimetype:
        images = convert_from_path(file_path)
    elif "image" in mimetype:
        images = [Image.open(file_path)]
    else:
        raise TypeError(f"file mimetype should be PDF or image. Yours is {mimetype}")

    bounding_boxes = [[] for _ in range(len(images))]
    text_labels = [[] for _ in range(len(images))]
    for ix, element in enumerate(elements):
        n_page = element.metadata.page_number - 1
        bounding_boxes[n_page].append(element.metadata.coordinates.to_dict()["points"])
        text_labels[n_page].append(f"{ix}. {element.category}")

    for page_ix, image in enumerate(images):
        if desired_width:
            aspect_ratio = images[0].width / images[0].height
            desired_height = desired_width / aspect_ratio
            fig, ax = plt.subplots(figsize=(desired_width, desired_height))
        else:
            fig, ax = plt.subplots()

        ax.imshow(image)

        for bbox, label in zip(bounding_boxes[page_ix], text_labels[page_ix]):
            x_min, y_min = bbox[0]
            x_max, y_max = bbox[2]
            width = x_max - x_min
            height = y_max - y_min
            rect = patches.Rectangle(
                (x_min, y_min),
                width,
                height,
                linewidth=1,
                edgecolor="black",
                facecolor="none",
            )
            label_clean = "".join([ch for ch in label if ch.isalpha()]).strip()
            rect.set_edgecolor(TYPE_TO_COLOUR_MAP[label_clean])
            rect.set_facecolor(colors.to_rgba(TYPE_TO_COLOUR_MAP[label_clean], alpha=0.04))
            ax.add_patch(rect)
            ax.text(
                x_min,
                y_min - 5,
                label,
                fontsize=12,
                weight="bold",
                color=TYPE_TO_COLOUR_MAP[label_clean],
                bbox={
                    "facecolor": (1.0, 1.0, 1.0, 0.7),
                    "edgecolor": (0.95, 0.95, 0.95, 0.0),
                    "pad": 0.5,
                },
            )

        if save_images or save_coordinates:
            if not output_folder:
                output_folder = "./"
                logging.warning("No output_folder defined. Storing predictions in relative path './'")

            if save_images:
                image_path = f"{output_folder}/images_with_bboxes"
                if not os.path.exists(image_path):
                    os.makedirs(image_path)
                plt.savefig(f'{image_path}/{file_path.split("/")[-1]}_{page_ix}.png')

            if save_coordinates:
                annotations_path = f"{output_folder}/bboxes_coordinates"
                if not os.path.exists(annotations_path):
                    os.makedirs(annotations_path)
                with open(
                    f'{annotations_path}/{file_path.split("/")[-1]}_{page_ix}.json', "w"
                ) as json_file:
                    json.dump(
                        [
                            {e_save.category: e_save.metadata.coordinates.to_dict()["points"]}
                            for e_save in elements
                        ],
                        json_file,
                    )

        if plot:
            plt.show()
        else:
            plt.close()
