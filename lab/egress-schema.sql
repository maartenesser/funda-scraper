CREATE TABLE IF NOT EXISTS observations (
 trial TEXT NOT NULL, bucket TEXT NOT NULL, total INTEGER NOT NULL,
 remote INTEGER NOT NULL, PRIMARY KEY(trial,bucket)
);
