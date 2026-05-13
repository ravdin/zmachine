from pathlib import Path
from .error import InvalidBlorbFileException, UnsupportedExecutableResourceException
from .logging import blorb_logger as logger

class BlorbFile:
    FORM = b'FORM'
    IFRS = b'IFRS'
    RIDX = b'RIdx'
    Exec = b'Exec'
    ZCOD = b'ZCOD'
    Snd  = b'Snd '
    Data = b'Data'
    Pict = b'Pict'
    PNG  = b'PNG '
    JPEG = b'JPEG'
    AIFF = b'AIFF'
    BLORB_EXTENSIONS = ['.blorb', '.zblorb', '.blb', '.zlb']
    
    def __init__(self, file_path: str):
        with open(file_path, 'rb') as f:
            self.data = f.read()
        
        self._sound_resources: dict[int, int] = {}
        self._picture_resources: dict[int, int] = {}
        self._executable_addr: int = 0
        try:
            self._parse_ridx()
        except Exception:
            raise InvalidBlorbFileException(file_path)

    @classmethod
    def detect_blorb_file(cls, path_name: str) -> tuple[str, bool]:
        path = Path(path_name)
        if not path.is_dir():
            return '', False
        for file_path in path.iterdir():
            if not file_path.is_file():
                continue
            for extension in cls.BLORB_EXTENSIONS:
                if file_path.match(f'*{extension}'):
                    file_size = file_path.stat().st_size
                    with file_path.open('rb') as f:
                        data = f.read(16)
                        if len(data) != 16:
                            continue
                        if data[0:4] == cls.FORM and \
                           int.from_bytes(data[4:8], "big") + 8 == file_size and \
                           data[8:12] == cls.IFRS and \
                           data[12:16] == cls.RIDX:
                            logger.info(f"Found blorb file {file_path}")
                            return str(file_path), True
        return '', False
    
    def _parse_ridx(self):
        # Assumptions: the RIDX chunk is first (as is supposed to be from the spec),
        # and the file has already been verified by detect_blorb_file.
        pos = 16
        chunk_count = int.from_bytes(self.data[pos + 4:pos + 8], 'big')
        pos += 8
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
    
    def get_image(self, number: int) -> bytes:
        """Get PNG or JPEG image data by resource number."""
        offset = self._picture_resources[number]
        chunk_type = self.data[offset:offset + 4]
        if chunk_type not in (self.JPEG, self.PNG):
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
