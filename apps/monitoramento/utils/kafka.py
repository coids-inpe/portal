import json
import time

from django.conf import settings
from kafka import KafkaConsumer, TopicPartition
from kafka.errors import KafkaError


class Kafka:
    def __init__(self, topic, last_lines):
        self.topic = topic
        self.last_lines = last_lines

    def get_kafka_topic(self):
        if not settings.KAFKA_SERVER:
            raise KafkaError("KAFKA_SERVER não configurado")

        consumer = KafkaConsumer(
            bootstrap_servers=settings.KAFKA_SERVER.split(","),
            enable_auto_commit=False,
        )
        try:
            partitions = consumer.partitions_for_topic(self.topic)
            if not partitions:
                return []

            # O cliente anterior lia apenas a primeira partição do tópico.
            partition = TopicPartition(self.topic, min(partitions))
            earliest = consumer.beginning_offsets([partition])[partition]
            latest = consumer.end_offsets([partition])[partition]
            if earliest == latest:
                return []

            consumer.assign([partition])
            consumer.seek(partition, max(earliest, latest - self.last_lines))
            result = []
            deadline = time.monotonic() + 2
            while len(result) < self.last_lines and time.monotonic() < deadline:
                records = consumer.poll(
                    timeout_ms=max(1, int((deadline - time.monotonic()) * 1000)),
                    max_records=self.last_lines - len(result),
                )
                if not records:
                    break
                result.extend(json.loads(message.value.decode()) for message in records.get(partition, []))
            return result
        finally:
            consumer.close()

