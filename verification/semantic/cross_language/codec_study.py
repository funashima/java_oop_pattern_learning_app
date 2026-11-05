"""Independent Python implementation of the bounded codec specification."""
from __future__ import annotations
from abc import ABC, abstractmethod
import json


class Encoder(ABC):
    family: str

    @abstractmethod
    def encode(self, x: int) -> str: ...


class Decoder(ABC):
    family: str

    @abstractmethod
    def decode(self, s: str) -> int: ...


class CodecFactory(ABC):
    @abstractmethod
    def create_encoder(self) -> Encoder: ...

    @abstractmethod
    def create_decoder(self) -> Decoder: ...


class DecimalEncoder(Encoder):
    family = "decimal"

    def encode(self, x: int) -> str:
        return str(x)


class HexEncoder(Encoder):
    family = "hex"

    def encode(self, x: int) -> str:
        return format(x, "x")


class DecimalDecoder(Decoder):
    family = "decimal"

    def decode(self, s: str) -> int:
        return int(s, 10)


class HexDecoder(Decoder):
    family = "hex"

    def decode(self, s: str) -> int:
        return int(s, 16)


class FaultyHexDecoder(Decoder):
    family = "hex"

    def decode(self, s: str) -> int:
        return int(s, 16) ^ 1


class DecimalFactory(CodecFactory):
    def create_encoder(self) -> Encoder:
        return DecimalEncoder()

    def create_decoder(self) -> Decoder:
        return DecimalDecoder()


class HexFactory(CodecFactory):
    def create_encoder(self) -> Encoder:
        return HexEncoder()

    def create_decoder(self) -> Decoder:
        return HexDecoder()


class MixedFactory(CodecFactory):
    def create_encoder(self) -> Encoder:
        return HexEncoder()

    def create_decoder(self) -> Decoder:
        return DecimalDecoder()


class FaultyHexFactory(CodecFactory):
    def create_encoder(self) -> Encoder:
        return HexEncoder()

    def create_decoder(self) -> Decoder:
        return FaultyHexDecoder()


def trial(name: str, requested: str, factory: CodecFactory, x: int) -> dict:
    e, d = factory.create_encoder(), factory.create_decoder()
    encoded = e.encode(x)
    decoded, error, raw_error = None, None, None
    try:
        decoded = d.decode(encoded)
    except ValueError as ex:
        error, raw_error = "ParseError", type(ex).__name__
    return dict(kind="trial", case=name, x=x, requested=requested,
                encoder_family=e.family, decoder_family=d.family,
                encoded=encoded, decoded=decoded, error=error, raw_error=raw_error)


def main() -> None:
    for x in range(256):
        for name, requested, factory in [
            ("decimal", "decimal", DecimalFactory()),
            ("hex", "hex", HexFactory()),
            ("mixed", "hex", MixedFactory()),
            ("wrong_family", "hex", DecimalFactory()),
            ("faulty_hex", "hex", FaultyHexFactory()),
        ]:
            print(json.dumps(trial(name, requested, factory, x)))
        decimal = DecimalEncoder().encode(x)
        converted = HexEncoder().encode(DecimalDecoder().decode(decimal))
        print(json.dumps(dict(kind="conversion", x=x, decimal=decimal, hex=converted)))
    left, right = {"value": 0}, {"value": 0}
    print(json.dumps(dict(kind="boundary", negative_division=(-1 * 8) // 10,
                          max_plus_one=2147483647 + 1,
                          value_equal=left == right, same_identity=left is right)))


if __name__ == "__main__":
    main()
