from types import SimpleNamespace

from apps.monitoramento.utils import kafka as kafka_module


def test_reads_latest_messages_from_first_partition(monkeypatch, settings):
    settings.KAFKA_SERVER = "broker:9092"

    class Consumer:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.partition = None
            self.offset = None
            self.closed = False

        def partitions_for_topic(self, topic):
            assert topic == "nodes"
            return {0, 1}

        def beginning_offsets(self, partitions):
            return {partitions[0]: 5}

        def end_offsets(self, partitions):
            return {partitions[0]: 9}

        def assign(self, partitions):
            self.partition = partitions[0]

        def seek(self, partition, offset):
            self.offset = offset

        def poll(self, **kwargs):
            assert kwargs["max_records"] == 2
            return {self.partition: [SimpleNamespace(value=b'{"n": 7}'), SimpleNamespace(value=b'{"n": 8}')]}

        def close(self):
            self.closed = True

    consumer = Consumer()
    monkeypatch.setattr(kafka_module, "KafkaConsumer", lambda **kwargs: consumer, raising=False)

    assert kafka_module.Kafka("nodes", 2).get_kafka_topic() == [{"n": 7}, {"n": 8}]
    assert consumer.partition.partition == 0
    assert consumer.offset == 7
    assert consumer.closed


def test_empty_topic_returns_no_messages(monkeypatch, settings):
    settings.KAFKA_SERVER = "broker:9092"

    class Consumer:
        closed = False

        def partitions_for_topic(self, topic):
            return {0}

        def beginning_offsets(self, partitions):
            return {partitions[0]: 0}

        def end_offsets(self, partitions):
            return {partitions[0]: 0}

        def close(self):
            self.closed = True

    consumer = Consumer()
    monkeypatch.setattr(kafka_module, "KafkaConsumer", lambda **kwargs: consumer, raising=False)

    assert kafka_module.Kafka("empty", 5).get_kafka_topic() == []
    assert consumer.closed
