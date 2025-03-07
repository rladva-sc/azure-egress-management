# Azure Metrics for Egress Monitoring

This document provides information about the metrics used in the Azure Egress Management tool.

## Available Metrics by Resource Type

### Network Interfaces

| Metric Key | Azure Metric Name | Display Name | Unit | Aggregation |
|------------|------------------|--------------|------|-------------|
| bytes_out | BytesOutPerSecond | Outbound Traffic | BytesPerSecond | Average |
| bytes_in | BytesInPerSecond | Inbound Traffic | BytesPerSecond | Average |
| packets_out | PacketsOutPerSecond | Outbound Packets | CountPerSecond | Average |
| packets_in | PacketsInPerSecond | Inbound Packets | CountPerSecond | Average |

### Virtual Machines

| Metric Key | Azure Metric Name | Display Name | Unit | Aggregation |
|------------|------------------|--------------|------|-------------|
| network_out | Network Out Total | Network Out Total | Bytes | Total |
| network_in | Network In Total | Network In Total | Bytes | Total |
| network_out_rate | Network Out | Network Out Rate | BytesPerSecond | Average |
| network_in_rate | Network In | Network In Rate | BytesPerSecond | Average |

### Load Balancers

| Metric Key | Azure Metric Name | Display Name | Unit | Aggregation |
|------------|------------------|--------------|------|-------------|
| bytes_out | ByteCount | Byte Count | Bytes | Total |
| packet_count | PacketCount | Packet Count | Count | Total |
| snat_connection_count | SnatConnectionCount | SNAT Connection Count | Count | Average |

### App Services

| Metric Key | Azure Metric Name | Display Name | Unit | Aggregation |
|------------|------------------|--------------|------|-------------|
| data_out | BytesSent | Data Out | Bytes | Total |
| data_in | BytesReceived | Data In | Bytes | Total |

## Understanding Metrics

### Aggregation Types

- **Average**: The average value over the aggregation interval
- **Total**: The sum of all values over the aggregation interval
- **Maximum**: The maximum value observed during the aggregation interval
- **Minimum**: The minimum value observed during the aggregation interval
- **Count**: The number of samples collected during the aggregation interval

### Units

- **Bytes**: Raw byte count
- **BytesPerSecond**: Bytes transferred per second
- **Count**: Raw count
- **CountPerSecond**: Count per second

## Using Metrics in the CLI

```bash
# Example: Monitor with default metrics
python -m src.main monitor --subscription YOUR_SUBSCRIPTION_ID

# Example: Store results to a file
python -m src.main monitor --subscription YOUR_SUBSCRIPTION_ID --output results.json

# Example: Monitor for a specific time period
python -m src.main monitor --subscription YOUR_SUBSCRIPTION_ID --days 14
```

## Extending with Custom Metrics

To add custom metrics, extend the `EgressMetricRegistry` class in `src/egress/metrics.py`.

```python
@staticmethod
def get_custom_resource_metrics() -> Dict[str, EgressMetricsDefinition]:
    """Get metrics for custom resources."""
    return {
        "custom_metric": EgressMetricsDefinition(
            name="CustomMetricName",
            display_name="Custom Metric",
            category="Custom",
            unit="Count",
            aggregation="Total",
            resource_type="Microsoft.Custom/resourceType",
            description="Description of the custom metric"
        )
    }
```
