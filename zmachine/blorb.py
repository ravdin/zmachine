from pathlib import Path
from dataclasses import dataclass
from .error import InvalidBlorbFileException, UnsupportedExecutableResourceException
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
    ratnum: int = 0
    ratden: int = 0
    minnum: int = 0
    minden: int = 0
    maxnum: int = 0
    maxden: int = 0

    @property
    def stdratio(self) -> float:
        if self.ratnum == self.ratden == 0:
            return 1.0
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

class BlorbFile:
    FORM = b'FORM'
    IFRS = b'IFRS'
    RIdx = b'RIdx'
    Exec = b'Exec'
    ZCOD = b'ZCOD'
    Snd  = b'Snd '
    Data = b'Data'
    Pict = b'Pict'
    PNG  = b'PNG '
    JPEG = b'JPEG'
    Rect = b'Rect'
    AIFF = b'AIFF'
    RelN = b'RelN'
    Reso = b'Reso'
    APal = b'APal'
    BLORB_EXTENSIONS = ['.blorb', '.zblorb', '.blb', '.zlb']
    
    def __init__(self, data: bytes):
        self.data = data
        
        pos = 0
        self._sound_resources: dict[int, int] = {}
        self._picture_resources: dict[int, int] = {}
        self._window_resolution: WindowResolution | None = None
        self._scalable_image_entries: dict[int, ScalableImage] = {}
        self._executable_addr: int = 0
        self._release_number = 0
        self._adaptive_pictures: set[int] = set()
        if len(data) > 0:
            pos = 12
            while pos < len(self.data):
                chunk_type = self.data[pos:pos + 4]
                chunk_len = int.from_bytes(self.data[pos + 4:pos + 8], "big")
                pad_byte = chunk_len & 1
                if chunk_type == self.RIdx:
                    self._parse_ridx(pos)
                elif chunk_type == self.RelN:
                    self._release_number = int.from_bytes(self.data[pos + 8:pos + 10], "big")
                elif chunk_type == self.Reso:
                    self._parse_resolution(pos)
                elif chunk_type == self.APal:
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
        if self._window_resolution is None:
            return 1.0
        # Calculate Elbow Room Factor.
        erf = min(window_width / self._window_resolution.standard_x, window_height / self._window_resolution.standard_y)
        default = ScalableImage(ratnum=1, ratden=1)
        scalable_image = self._scalable_image_entries.get(number, default)
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
                if file_path.match(f'*{extension}'):
                    with file_path.open('rb') as f:
                        data = f.read()
                        if len(data) < 16:
                            continue
                        if data[0:4] == cls.FORM and \
                           int.from_bytes(data[4:8], "big") + 8 == len(data) and \
                           data[8:12] == cls.IFRS and \
                           data[12:16] == cls.RIdx:
                            logger.info(f"Found blorb file {file_path}")
                            try:
                                return cls(data)
                            except Exception:
                                raise InvalidBlorbFileException(str(file_path))
        return cls(b'')
    
    def _parse_ridx(self, pos: int):
        # Assumptions: the RIDX chunk is first (as is supposed to be from the spec),
        # and the file has already been verified by detect_blorb_file.
        chunk_count = int.from_bytes(self.data[pos + 8:pos + 12], 'big')
        pos += 12
        for _ in range(chunk_count):
            usage = self.data[pos:pos + 4]
            index = int.from_bytes(self.data[pos + 4:pos + 8], 'big')
            start = int.from_bytes(self.data[pos + 8:pos + 12], 'big')

            if usage == self.Snd:
                self._sound_resources[index] = start
            elif usage == self.Pict:
                self._picture_resources[index] = start
            elif usage == self.Exec:
                self._executable_addr = start
            pos += 12

    def _parse_resolution(self, pos: int):
        chunk_len = int.from_bytes(self.data[pos + 4:pos + 8], 'big')
        standard_x = int.from_bytes(self.data[pos + 8:pos + 12], 'big')
        standard_y = int.from_bytes(self.data[pos + 12:pos + 16], 'big')
        min_x = int.from_bytes(self.data[pos + 16:pos + 20], 'big')
        min_y = int.from_bytes(self.data[pos + 20:pos + 24], 'big')
        max_x = int.from_bytes(self.data[pos + 24:pos + 28], 'big')
        max_y = int.from_bytes(self.data[pos + 28:pos + 32], 'big')
        self._window_resolution = WindowResolution(
            standard_x=standard_x,
            standard_y=standard_y,
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y
        )
        entry_pos = pos + 32
        while entry_pos < pos + chunk_len + 8:
            number = int.from_bytes(self.data[entry_pos:entry_pos + 4])
            ratnum = int.from_bytes(self.data[entry_pos + 4:entry_pos + 8])
            ratden = int.from_bytes(self.data[entry_pos + 8:entry_pos + 12])
            minnum = int.from_bytes(self.data[entry_pos + 12:entry_pos + 16])
            minden = int.from_bytes(self.data[entry_pos + 16:entry_pos + 20])
            maxnum = int.from_bytes(self.data[entry_pos + 20:entry_pos + 24])
            maxden = int.from_bytes(self.data[entry_pos + 24:entry_pos + 28])
            self._scalable_image_entries[number] = ScalableImage(
                ratnum=ratnum,
                ratden=ratden,
                minnum=minnum,
                minden=minden,
                maxnum=maxnum,
                maxden=maxden
            )
            entry_pos += 28

    def _parse_adaptive_palette(self, pos: int):
        chunk_len = int.from_bytes(self.data[pos + 4:pos + 8], 'big')
        entry_pos = pos + 8
        while entry_pos < pos + chunk_len + 8:
            picture_number = int.from_bytes(self.data[entry_pos:entry_pos + 4], 'big')
            self._adaptive_pictures.add(picture_number)
            entry_pos += 4
    
    def get_story_data(self) -> bytes:
        """Extract Z-code story from ZCOD chunk."""
        if self._executable_addr == 0:
            return b''
        offset = self._executable_addr
        chunk_type = self.data[offset:offset + 4]
        if chunk_type != self.ZCOD:
            raise UnsupportedExecutableResourceException(chunk_type)
        chunk_len = int.from_bytes(self.data[offset + 4:offset + 8], 'big')
        logger.info(f'Fetching {chunk_type!r} executable from address {offset:x}')
        return self.data[offset + 8:offset + 8 + chunk_len]
    
    def get_picture_data(self, number: int) -> bytes:
        """Get PNG or JPEG image data by resource number."""
        if number not in self._picture_resources:
            return b''
        offset = self._picture_resources[number]
        chunk_type = self.data[offset:offset + 4]
        if chunk_type not in (self.JPEG, self.PNG, self.Rect):
            logger.warning(f'Chunk type "{chunk_type!r}" not recognized')
            return b''
        chunk_len = int.from_bytes(self.data[offset + 4:offset + 8], 'big')
        logger.info(f'Fetching {chunk_type!r} image from address {offset:x}')
        return self.data[offset + 8:offset + 8 + chunk_len]

    def get_sound_data(self, number: int) -> bytes:
        if number not in self._sound_resources:
            return b''
        offset = self._sound_resources[number]
        chunk_type = self.data[offset:offset + 4]
        if chunk_type == self.FORM:
            chunk_len = int.from_bytes(self.data[offset + 4:offset + 8], 'big')
            return self.data[offset:offset + 8 + chunk_len]
        return b''
