# C4 diagrams

Sources: `*.puml` (C4-PlantUML from the PlantUML stdlib). Rendered SVGs in `svg/`; the page `index.html`
inlines them and adds the business/architect narrative (state as of 2026-09-05, main 191532e).

Re-render (no Graphviz needed — the Smetana layout engine is built in):

    java -Djava.awt.headless=true -jar ~/.cache/guidefold/tools/plantuml.jar -tsvg -charset UTF-8 -o svg *.puml

Rules that bit us: a nested `Deployment_Node(...) { Container(...) }` must span separate lines, tags on nodes
need `AddNodeTag`, and a literal `$` inside a label is read as a preprocessor variable.
