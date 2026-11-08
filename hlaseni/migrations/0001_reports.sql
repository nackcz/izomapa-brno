-- hlášení nepřesností z mapy
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created TEXT NOT NULL DEFAULT (datetime('now')),
  target TEXT NOT NULL,          -- budova "b:<id>" nebo "c0_-1:123" nebo místo "pt:50.7698,15.0584"
  title TEXT,                    -- název / adresa v okamžiku hlášení
  kind TEXT NOT NULL,            -- zatím vždy 'text'
  note TEXT,
  lon REAL, lat REAL,
  who TEXT NOT NULL,             -- hash IP + den (ne IP samotná)
  status TEXT NOT NULL DEFAULT 'nove',  -- nove | vyreseno | zamitnuto
  dev TEXT                       -- hash IP bez data (limit 3 hlášení za hodinu)
);
CREATE INDEX IF NOT EXISTS reports_target ON reports(target);
CREATE UNIQUE INDEX IF NOT EXISTS reports_once ON reports(target, who);
CREATE INDEX IF NOT EXISTS reports_dev ON reports(dev, created);
