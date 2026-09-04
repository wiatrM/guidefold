# forge

Forge is Meridian's data-integration platform: it takes data from source systems and turns it into
governed datasets and a queryable ontology that the Atlas analyst workspace reads. Its three main parts
are the **ontology** (object types, link types, and properties declared in YAML and compiled into Postgres
tables), **pipelines** (PySpark batch jobs in the `meridian_pipelines` package plus Spark Structured
Streaming consumers fed by Kafka), and **datasets** (schema-registered outputs with mandatory lineage
tags pointing back at the pipeline that produced them).

The node is owned by forge-platform, which sets the dataset naming, schema registry, and lineage rules
for the whole platform. Sub-teams own the child nodes: ontology-team (`forge.ontology`) owns object type
modelling and migrations, pipelines-team (`forge.pipelines`) owns the batch pipeline framework and its
test harness, and streaming-team (`forge.pipelines.streaming`) owns Kafka topics and ingestion consumers.
