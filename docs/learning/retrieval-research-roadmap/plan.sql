BEGIN TRANSACTION;
CREATE TABLE learning_plan(stage_order INTEGER PRIMARY KEY, stage TEXT, weeks_range TEXT, weeks INTEGER, outcome TEXT);
INSERT INTO "learning_plan" VALUES(1,'01 Python','1–4',4,'Skrypt JSONL → metryki');
INSERT INTO "learning_plan" VALUES(2,'02 Matematyka i ML','5–8',4,'Notatnik o podobieństwie i błędzie');
INSERT INTO "learning_plan" VALUES(3,'03 Machine Learning','9–17',9,'Eksperyment train/dev/test');
INSERT INTO "learning_plan" VALUES(4,'04 Sieci i PyTorch','18–21',4,'Trening i checkpoint');
INSERT INTO "learning_plan" VALUES(5,'05 IR i RAG','22–25',4,'Baseline BM25 i ewaluator');
INSERT INTO "learning_plan" VALUES(6,'06 Transformery','26–28',3,'Audyt wejścia modelu');
INSERT INTO "learning_plan" VALUES(7,'07 Własny retriever','29–33',5,'Dostrojony bi-encoder');
INSERT INTO "learning_plan" VALUES(8,'08 Reranker','34–36',3,'Cross-encoder i bramka jakości');
INSERT INTO "learning_plan" VALUES(9,'09 Agent i koszt','37–39',3,'Pipeline z abstencją i budżetem');
INSERT INTO "learning_plan" VALUES(10,'10 Badanie i artykuł','40–44',5,'Reprodukcja, ablacje, tekst');
COMMIT;

SELECT stage_order, stage, weeks_range, weeks, weeks * 15 AS hours, outcome FROM learning_plan ORDER BY stage_order;
