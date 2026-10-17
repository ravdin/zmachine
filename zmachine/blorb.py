import struct
from pathlib import Path
from dataclasses import dataclass
from .protocol import PictureResource
from .enums import ChunkId, ResourceType
from .error import InvalidBlorbFileException
from .logging import blorb_logger as logger

@dataclass(frozen=True)
class WindowResolution:
    standard_x: int = 0
    standard_y: int = 0
    min_x: int = 0
    min_y: int = 0
    max_x: int = 0
    max_y: int = 0

@dataclass(frozen=True)
class ScalableImage:
    ratnum: int = 1
    ratden: int = 1
    minnum: int = 0
    minden: int = 0
    maxnum: int = 0
    maxden: int = 0

    @property
    def stdratio(self) -> float:
        return self.ratnum / self.ratden
    
    @property
    def minratio(self) -> float:
        if self.minnum == self.minden == 0:
            return 0
        return self.minnum / self.minden
    
    @property
    def maxratio(self) -> float:
        if self.maxnum == self.maxden == 0:
            return float('inf')
        return self.maxnum / self.maxden

    @property
    def is_valid(self) -> bool:
        # Per the spec, minratio or maxratio can be 0/0 (meaning no lower or upper limit),
        # but it's invalid for half of a fraction to be zero.
        # It's not clear how to handle if ratnum or ratden are zero, but we'll assume this
        # is also invalid.
        if self.ratnum == 0 or self.ratden == 0:
            return False
        if self.minnum == 0 and self.minden != 0:
            return False
        if self.minnum != 0 and self.minden == 0:
            return False
        if self.maxnum == 0 and self.maxden != 0:
            return False
        if self.maxnum != 0 and self.maxden == 0:
            return False
        return True

class BlorbFile:
    BLORB_EXTENSIONS = ['.blorb', '.zblorb', '.blb', '.zlb']
    
    def __init__(self, data: bytes):
        self.data = data
        
        pos = 0
        self._sound_resources: dict[int, int] = {}
        self._picture_resources: dict[int, int] = {}
        self._window_resolution: WindowResolution | None = None
        self._scalable_image_entries: dict[int, ScalableImage] = {}
        self._release_number = 0
        self._adaptive_pictures: set[int] = set()
        if len(data) > 0:
            pos = 12
            while pos < len(self.data):
                chunk_type, chunk_len = struct.unpack_from(">4sI", self.data, pos)
                pad_byte = chunk_len & 1
                if chunk_type == ChunkId.RIdx:
                    self._parse_ridx(pos)
                elif chunk_type == ChunkId.RelN:
                    self._release_number, = struct.unpack_from(">H", self.data, pos + 8)
                elif chunk_type == ChunkId.Reso:
                    self._parse_resolution(pos)
                elif chunk_type == ChunkId.APal:
                    self._parse_adaptive_palette(pos)
                pos += chunk_len + pad_byte + 8
        
    @property
    def release_number(self) -> int:
        return self._release_number
    
    @property
    def picture_count(self) -> int:
        return len(self._picture_resources)
    
    def is_valid_picture(self, number: int) -> bool:
        return number in self._picture_resources
    
    def is_adaptive_picture(self, number: int) -> bool:
        return number in self._adaptive_pictures
    
    def get_scaling_ratio(self, number: int, window_width: int, window_height: int) -> float:
        if self._window_resolution is None or number not in self._scalable_image_entries:
            return 1.0
        # Calculate Elbow Room Factor.
        erf = min(window_width / self._window_resolution.standard_x, window_height / self._window_resolution.standard_y)
        scalable_image = self._scalable_image_entries[number]
        ratio = erf * scalable_image.stdratio
        if ratio < scalable_image.minratio:
            return scalable_image.minratio
        elif ratio > scalable_image.maxratio:
            return scalable_image.maxratio
        return ratio

    @classmethod
    def detect_blorb_file(cls, path_name: str) -> 'BlorbFile':
        path = Path(path_name)
        if not path.is_dir():
            return cls(b'')
        for file_path in path.iterdir():
            if not file_path.is_file():
                continue
            for extension in cls.BLORB_EXTENSIONS:
                if file_path.match(f'*{extension}', case_sensitive = False):
                    with file_path.open('rb') as f:
                        data = f.read()
                        if len(data) < 16:
                            continue
                        if data[0:4] == ChunkId.FORM and \
                           int.from_bytes(data[4:8], "big") + 8 == len(data) and \
                           data[8:12] == ChunkId.IFRS and \
                           data[12:16] == ChunkId.RIdx:
                            logger.info(f"Found blorb file {file_path}")
                            try:
                                return cls(data)
                            except Exception as e:
                                raise InvalidBlorbFileException(str(file_path)) from e
        return cls(b'')
    
    def _parse_ridx(self, pos: int):
        # Assumptions: the RIDX chunk is first (as is supposed to be from the spec),
        # and the file has already been verified by detect_blorb_file.
        chunk_count, = struct.unpack_from(">I", self.data, pos + 8)
        pos += 12
        for _ in range(chunk_count):
            usage, index, start = struct.unpack_from(">4sII", self.data, pos)
            if usage == ResourceType.Snd:
                self._sound_resources[index] = start
            elif usage == ResourceType.Pict:
                self._picture_resources[index] = start
            pos += 12

    def _parse_resolution(self, pos: int):
        chunk_len, = struct.unpack_from(">I", self.data, pos + 4)
        window_resolution = WindowResolution(
            *struct.unpack_from(">6I", self.data, pos + 8)
        )
        if window_resolution.standard_x == 0 or window_resolution.standard_y == 0:
            # This shouldn't be the standard window size, ignore if this is the case for some reason.
            logger.warning(f'Invalid window resolution {window_resolution.standard_x}x{window_resolution.standard_y}')
            return
        self._window_resolution = window_resolution
        entry_pos = pos + 32
        while entry_pos < pos + chunk_len + 8:
            number, = struct.unpack_from(">I", self.data, entry_pos)
            entry = ScalableImage(
                *struct.unpack_from(">6I", self.data, entry_pos + 4)
            )
            if entry.is_valid:
                self._scalable_image_entries[number] = entry
            else:
                logger.warning(f'Invalid scale resolution entry {number}')
            entry_pos += 28

    def _parse_adaptive_palette(self, pos: int):
        chunk_len, = struct.unpack_from(">I", self.data, pos + 4)
        entry_pos = pos + 8
        while entry_pos < pos + chunk_len + 8:
            picture_number, = struct.unpack_from(">I", self.data, entry_pos)
            self._adaptive_pictures.add(picture_number)
            entry_pos += 4
    
    def get_picture_data(self, number: int) -> PictureResource | None:
        """Get PNG or JPEG image data by resource number."""
        if number not in self._picture_resources:
            return None
        offset = self._picture_resources[number]
        chunk_id, chunk_len = struct.unpack_from(">4sI", self.data, offset)
        if chunk_id == ChunkId.Rect:
            width, height = struct.unpack_from(">II", self.data, offset + 8)
            data = b''
        elif chunk_id in (ChunkId.JPEG, ChunkId.PNG):
            width, height = 0, 0
            data = self.data[offset + 8:offset + 8 + chunk_len]
        else:
            logger.warning(f'Chunk ID "{chunk_id!r}" not recognized')
            return None
        logger.info(f'Fetching {chunk_id!r} image from address {offset:x}')
        return PictureResource(
            chunk_id = ChunkId(chunk_id),
            data = data,
            width = width,
            height = height
        )
    
    def get_sound_data(self, number: int) -> bytes:
        if number not in self._sound_resources:
            return b''
        offset = self._sound_resources[number]
        chunk_type = self.data[offset:offset + 4]
        if chunk_type == ChunkId.FORM:
            chunk_len, = struct.unpack_from(">I", self.data, offset + 4)
            return self.data[offset:offset + 8 + chunk_len]
        return b''
