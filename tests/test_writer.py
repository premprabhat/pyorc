import pytest

import io
import tempfile
import math
from datetime import date, datetime, timezone
from decimal import Decimal

from pyorc import Writer, Reader, typedescription, ParseError, TypeKind, StructRepr
from pyorc.converters import ORCConverter


def test_open_file():
    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        with pytest.raises(ParseError):
            _ = Writer(fp, "int")
        with open(fp.name, "rb") as fp2:
            with pytest.raises(io.UnsupportedOperation):
                _ = Writer(fp2, "int")
    with tempfile.NamedTemporaryFile(mode="wb") as fp:
        writer = Writer(fp, "int")
        assert isinstance(writer, Writer)
    with pytest.raises(TypeError):
        _ = Writer(0, "int")


def test_init():
    data = io.BytesIO()
    with pytest.raises(TypeError):
        _ = Writer(data, 0)
    with pytest.raises(TypeError):
        _ = Writer(data, "int", batch_size=-1)
    with pytest.raises(TypeError):
        _ = Writer(data, "int", batch_size="fail")
    with pytest.raises(TypeError):
        _ = Writer(data, "int", batch_size=1000, stripe_size=-1)
    with pytest.raises(TypeError):
        _ = Writer(data, "int", batch_size=1000, stripe_size="fail")
    with pytest.raises(ValueError):
        _ = Writer(data, "int", batch_size=1000, stripe_size=5000, compression=-1)
    with pytest.raises(ValueError):
        _ = Writer(data, "int", batch_size=1000, stripe_size=5000, compression="wrong")
    with pytest.raises(ValueError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=-1,
        )
    with pytest.raises(ValueError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy="fail",
        )
    with pytest.raises(TypeError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=0,
            compression_block_size=-1,
        )
    with pytest.raises(ValueError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=0,
            compression_block_size=1,
            bloom_filter_columns=["0", 1, 3.4],
        )
    with pytest.raises(KeyError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=0,
            compression_block_size=1,
            bloom_filter_columns=["0"],
        )
    with pytest.raises(TypeError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=0,
            compression_block_size=1,
            bloom_filter_columns=[0],
            bloom_filter_fpp="wrong",
        )
    with pytest.raises(ValueError):
        _ = Writer(
            data,
            "int",
            batch_size=1000,
            stripe_size=5000,
            compression=0,
            compression_strategy=0,
            compression_block_size=1,
            bloom_filter_columns=[0],
            bloom_filter_fpp=2.0,
        )
    writer = Writer(
        data,
        "int",
        batch_size=1000,
        stripe_size=5000,
        compression=0,
        compression_strategy=0,
        compression_block_size=1,
        bloom_filter_columns=[0],
        bloom_filter_fpp=0.5,
    )
    assert isinstance(writer, Writer)


def test_write():
    data = io.BytesIO()
    writer = Writer(data, "struct<col0:int,col1:string,col2:double>")
    records = [(1, "Test A", 2.13), (2, "Test B", 0.123213), (3, "Test C", 123.011234)]
    for rec in records:
        writer.write(rec)
    writer.close()
    data.seek(0)
    reader = Reader(data)
    assert reader.read() == records


TESTDATA = [
    ("string", 0),
    ("string", b"\x10\x13"),
    ("int", "str example"),
    ("bigint", 3.14),
    ("binary", "str example"),
    ("binary", 12),
    ("float", "str example"),
    ("double", b"\x42\x32"),
    ("boolean", "str example"),
    ("timestamp", "str example"),
    ("timestamp", 102112),
    ("date", "str example"),
    ("date", 123),
    ("decimal(10,5)", "str example"),
    ("decimal(36,8)", 1024),
]


@pytest.mark.parametrize("orc_type,value", TESTDATA)
def test_write_wrong_primitive_type(orc_type, value):
    data = io.BytesIO()
    writer = Writer(data, orc_type)
    with pytest.raises(TypeError):
        writer.write(value)


TESTDATA = [
    ("string", ["Not so very very very long text", "Another text", None, "Onemore"]),
    ("binary", [b"\x10\x13\x45\x95\xa4", b"\x34\x56\x45", None, b"\44\x23\x34\xa2"]),
    ("int", [100, None, 1231, 1234]),
    ("bigint", [3123213123, 12321344, 1231238384, None]),
    ("float", [3.14, 2.1, None, 5.5]),
    ("double", [3.14159265359, None, 4.12345678, 4.863723423]),
    ("boolean", [None, False, True, False]),
    (
        "timestamp",
        [
            datetime(2019, 4, 19, 12, 58, 59, tzinfo=timezone.utc),
            datetime(1914, 6, 28, 10, 45, 0, tzinfo=timezone.utc),
            None,
            datetime(2001, 3, 12, 10, 45, 21, 12, tzinfo=timezone.utc),
        ],
    ),
    ("date", [date(1909, 12, 8), None, date(2038, 10, 11), date(2019, 11, 11)]),
    (
        "decimal(10,7)",
        [None, Decimal("0.999999"), Decimal("123.4567890"), Decimal("99.1780000")],
    ),
    (
        "decimal(38,6)",
        [Decimal("999989898.1234"), Decimal("1.245678e24"), None, Decimal("1.2145e28")],
    ),
]


@pytest.mark.parametrize("orc_type,values", TESTDATA)
def test_write_primitive_type(orc_type, values):
    data = io.BytesIO()
    writer = Writer(data, orc_type)
    for rec in values:
        writer.write(rec)
    writer.close()

    data.seek(0)
    reader = Reader(data)
    if orc_type == "float":
        result = reader.read()
        assert len(result) == len(values)
        for res, exp in zip(result, values):
            if exp is None:
                assert res is None
            else:
                assert math.isclose(res, exp, rel_tol=1e-07, abs_tol=0.0)
    else:
        assert reader.read() == values


TESTDATA = [
    ("map<string,string>", "string"),
    ("map<string,int>", False),
    ("map<int,string>", ["a", "b", "c"]),
    ("map<int,string>", {"0": 0, "1": 1}),
    ("array<int>", 0),
    ("array<string>", [False, True, False]),
    ("array<boolean>", "false"),
    ("uniontype<int,float>", "string"),
    ("uniontype<int,string>", 2.4),
    ("uniontype<string,boolean>", [0, 2]),
    ("struct<col0:int,col1:string>", "string"),
    ("struct<col0:string,col1:int>", 0),
    ("struct<col0:string,col1:int>", [0, 1, 2]),
    ("struct<col0:string,col1:int>", (0,)),
    ("struct<col0:string,col1:int>", {"col0": "a", "col1": 0}),
]


@pytest.mark.parametrize("orc_type,value", TESTDATA)
def test_write_wrong_complex_type(orc_type, value):
    data = io.BytesIO()
    writer = Writer(data, orc_type)
    with pytest.raises(
        (TypeError, ValueError)
    ):  # Dict construction might raise ValueError as well.
        writer.write(value)


TESTDATA = [
    (
        "map<string,string>",
        [{"a": "b", "c": "d"}, {"e": "f", "g": "h", "i": "j"}, None, {"k": "l"}],
    ),
    (
        "map<string,int>",
        [
            {"zero": 0, "one": 1},
            None,
            {"two": 2, "tree": 3},
            {"one": 1, "two": 2, "nill": None},
        ],
    ),
    ("array<int>", [[0, 1, 2, 3], [4, 5, 6, 7, 8], None, [9, 10, 11, 12]]),
    (
        "array<string>",
        [
            ["First text", "Second text", "Third text", None],
            None,
            ["Fourth text", "Fifth text", "Sixth text"],
            ["Seventh text", "Last text"],
        ],
    ),
    ("uniontype<int,string>", ["string", 1, "text", 2, None]),
    (
        "struct<col0:int,col1:string>",
        [
            {"col0": 0, "col1": "String"},
            {"col0": 1, "col1": "String 2"},
            None,
            {"col0": 2, "col1": None},
        ],
    ),
]


@pytest.mark.parametrize("orc_type,values", TESTDATA)
def test_write_complex_type(orc_type, values):
    data = io.BytesIO()
    writer = Writer(data, orc_type, struct_repr=StructRepr.DICT)
    for rec in values:
        writer.write(rec)
    writer.close()

    data.seek(0)
    reader = Reader(data, struct_repr=StructRepr.DICT)
    assert reader.read() == values


TESTDATA = [
    ("int", 42),
    ("bigint", 560000000000001),
    ("float", 3.14),
    ("double", math.e),
    ("string", "test"),
    ("binary", b"\x23\x45\x45"),
    ("varchar(4)", "four"),
    ("timestamp", datetime(2019, 11, 10, 12, 59, 59, 100, tzinfo=timezone.utc)),
    ("date", date(2010, 9, 1)),
    ("decimal(10,0)", Decimal("1000000000")),
    ("array<int>", [0, 1, 2, 3]),
    ("map<string,string>", {"test": "example"}),
    ("struct<col0:int,col1:string>", (0, "test")),
]


@pytest.mark.parametrize("orc_type,value", TESTDATA)
def test_write_nones(orc_type, value):
    data = io.BytesIO()
    writer = Writer(data, orc_type, batch_size=20)
    for _ in range(100):
        writer.write(value)
    for _ in range(100):
        writer.write(None)
    writer.close()

    data.seek(0)
    reader = Reader(data, batch_size=30)
    non_nones = reader.read(100)
    nones = reader.read(100)
    assert len(reader) == 200
    if orc_type in ("float", "double"):
        assert math.isclose(non_nones[0], value, rel_tol=1e-07, abs_tol=0.0)
        assert math.isclose(non_nones[-1], value, rel_tol=1e-07, abs_tol=0.0)
    else:
        assert non_nones[0] == value
        assert non_nones[-1] == value
    assert all(row is not None for row in non_nones)
    assert all(row is None for row in nones)


def test_context_manager():
    data = io.BytesIO()
    records = [
        {"col0": 1, "col1": "Test A", "col2": 2.13},
        {"col0": 2, "col1": "Test B", "col2": 0.123213},
        {"col0": 3, "col1": "Test C", "col2": 123.011234},
    ]
    with Writer(
        data, "struct<col0:int,col1:string,col2:double>", struct_repr=StructRepr.DICT
    ) as writer:
        for rec in records:
            writer.write(rec)
    data.seek(0)
    reader = Reader(data, struct_repr=StructRepr.DICT)
    assert reader.read() == records


def test_current_row():
    data = io.BytesIO()
    writer = Writer(data, "struct<col0:int,col1:string,col2:double>")
    assert writer.current_row == 0
    writer.write((0, "Test A", 0.0001))
    assert writer.current_row == 1
    for i in range(10):
        writer.write((i, "Test A", 0.0001))
    assert writer.current_row == 11
    writer.close()
    data.seek(0)
    reader = Reader(data)
    assert writer.current_row == len(reader)


def test_schema():
    schema_str = "struct<col0:int,col1:string>"
    data = io.BytesIO()
    writer = Writer(data, schema_str)

    assert str(writer.schema) == schema_str
    with pytest.raises(AttributeError):
        writer.schema = "fail"
    with pytest.raises(AttributeError):
        del writer.schema

    schema = writer.schema
    del writer
    assert isinstance(schema, typedescription)
    assert schema.kind == TypeKind.STRUCT


def test_writerows():
    data = io.BytesIO()
    writer = Writer(data, "int")
    rows = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    res = writer.writerows(rows)
    writer.close()
    assert res == len(rows)

    data.seek(0)
    reader = Reader(data)
    assert list(rows) == reader.read()


def test_struct_repr():
    data = io.BytesIO()
    writer = Writer(data, "struct<a:int>")
    with pytest.raises(TypeError):
        writer.write({"a": 1})
    writer = Writer(data, "struct<a:int>", struct_repr=StructRepr.DICT)
    with pytest.raises(TypeError):
        writer.write((1,))
    with pytest.raises(TypeError):
        writer.write({"a": "b"})


class TestConverter(ORCConverter):
    @staticmethod
    def to_orc(obj):
        seconds, nanoseconds = obj
        return (seconds, nanoseconds)

    @staticmethod
    def from_orc(seconds, nanoseconds):
        pass


def test_converter():
    data = io.BytesIO()
    seconds = 1500000
    nanoseconds = 101000
    exp_date = date(2000, 1, 1)
    record = ((seconds, nanoseconds), exp_date)
    with Writer(
        data,
        "struct<col0:timestamp,col1:date>",
        converters={TypeKind.TIMESTAMP: TestConverter},
    ) as writer:
        writer.write(record)

    data.seek(0)
    reader = Reader(data)
    assert next(reader) == (
        datetime.fromtimestamp(seconds, timezone.utc).replace(
            microsecond=nanoseconds // 1000
        ),
        exp_date,
    )


def test_metadata():
    data = io.BytesIO()
    with Writer(data, "int") as writer:
        writer.set_metadata(test="test1".encode("UTF-8"), meta=b"\x30\x40\x50\x60")
        writer.set_metadata(test="test2".encode("UTF-8"))
        with pytest.raises(TypeError):
            writer.set_metadata(meta="string")
    reader = Reader(data)
    assert len(reader) == 0
    assert reader.metadata == {
        "test": "test2".encode("UTF-8"),
        "meta": b"\x30\x40\x50\x60",
    }
