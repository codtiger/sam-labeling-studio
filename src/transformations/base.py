from abc import ABC
from enum import Enum

class TransformationType(Enum):
    IMAGE = "image"
    MASK = "mask"
    ANNOTATION = "annotation"

class BaseTransformation(ABC):
    """"
    Base class for all image, mask, and annotation transformations.

    """
    def __init__(self, transform_type: TransformationType, name: str, **kwargs):
        self.transform_type = transform_type
        self.name = name
        self.params = kwargs
        super().__init__()

    def apply(self, data):
        """
        Apply the transformation to the given data.

        Parameters:
        data: The data to be transformed (e.g., image, mask, annotation).

        Returns:
        Transformed data.
        """
        raise NotImplementedError("Subclasses must implement this method.")
    
    def reset(self, data):
        """
        Reset the transformation to its original state.

        Parameters:
        data: The data to be reset (e.g., image, mask, annotation).

        Returns:
        Original data.
        """
        raise NotImplementedError("Subclasses must implement this method.")
    def __repr__(self,):
        return f"{self.__class__.__name__}(type={self.transform_type}, name={self.name}, \
                 params={self.params})"