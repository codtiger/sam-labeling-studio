from .base import BaseTransformation

class PolygonOffsetTransformation(BaseTransformation):
    """
    Transformation to offset polygon coordinates by a specified amount.

    Parameters:
    offset_x (float): The amount to offset in the x-direction.
    offset_y (float): The amount to offset in the y-direction.
    """
    def __init__(self, offset_x: float = 0.0, offset_y: float = 0.0, desc:str="poly_offset", **kwargs):
        super().__init__(transform_type="mask", name="PolygonOffset", 
                         offset_x=offset_x, offset_y=offset_y, **kwargs)
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.description = desc

    def apply(self, objects: list[dict]):
        """
        Apply the offset transformation to a list of polygons.
            param objects (list[dict]): List of object dicts, containing polygon under "object"
                                         and optionally "center

            returns: (list[list[tuple]]): Transformed polygons with applied offsets.
        """
        for object in objects:
            object["polygon"] = [[x + self.offset_x, y + self.offset_y]
                                   for x, y in object["polygon"]]
            if "center" in object and object["center"]:
                object["center"] = [object["center"][0] + self.offset_x, 
                                        object["center"][1] + self.offset_y]       
                
    def reset(self, objects: list[dict]):
        """
        Reset the offset transformation by reversing the applied offsets.
            param polygons (list[list[tuple]]): List of polygons, where each polygon is represented
                                           as a list of (x, y) tuples.
            returns: list of list of tuples: Original polygons with offsets reversed.
        """
        for object in objects:
            object["polygon"] = [[x - self.offset_x, y - self.offset_y] for x, y in object["polygon"]]
            if "center" in object and object["center"]:
                object["center"] = [object["center"][0] - self.offset_x, 
                                        object["center"][1] - self.offset_y]
    
    def __str__(self, ):
        return f"PolygonOffset ΔX: {self.offset_x}  ΔY: {self.offset_y},{self.description})"