#include "Writer.h"
#include "PyORCStream.h"

Writer::Writer(py::object fileo, py::object schema_str, py::object batch_size,
               py::object stripe_size, py::object compression, py::object compression_strategy) {
    currentRow = 0;
    batchItem = 0;
    std::string schstr = py::cast<std::string>(schema_str);
    std::unique_ptr<orc::Type> schema(orc::Type::buildTypeFromString(schstr));
    orc::WriterOptions options;
    uint64_t stripeSize = py::cast<uint64_t>(stripe_size);
    auto comp = static_cast<orc::CompressionKind>(py::cast<int>(compression));
    auto compStrategy = static_cast<orc::CompressionStrategy>(py::cast<int>(compression_strategy));

    options = options.setCompression(comp);
    options = options.setCompressionStrategy(compStrategy);
    options = options.setStripeSize(stripeSize);

    outStream = std::unique_ptr<orc::OutputStream>(new PyORCOutputStream(fileo));
    writer = createWriter(*schema, outStream.get(), options);
    batchSize = py::cast<uint64_t>(batch_size);
    batch = writer->createRowBatch(batchSize);
    converter = createConverter(schema.get());
}

void Writer::write(py::object row) {
    converter->write(batch.get(), batchItem, row);
    currentRow++; batchItem++;

    if (batchItem == batchSize) {
        writer->add(*batch);
        converter->clear();
        batchItem = 0;
    }
}

void Writer::close() {
    if (batchItem != 0) {
        writer->add(*batch);
        converter->clear();
        batchItem = 0;
    }
    writer->close();
}