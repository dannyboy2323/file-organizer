Column Name               Data Type            Max Length      Nullable
----------------------------------------------------------------------
id                        integer              N/A             NO
gdrive_path               text                 N/A             YES
s3_path                   text                 N/A             YES
orig_name                 text                 N/A             YES
name                      text                 N/A             YES
gdrive_id                 text                 N/A             YES
uuid                      text                 N/A             YES
file_size                 bigint               N/A             YES
length                    real                 N/A             YES
type                      text                 N/A             YES
subjects                  text                 N/A             YES
extension                 text                 N/A             YES
segments                  text                 N/A             YES
tags                      text                 N/A             YES
summary                   text                 N/A             YES
trailer                   text                 N/A             YES
file_created              timestamp without time zone N/A             YES
file_edited               timestamp without time zone N/A             YES
db_added                  timestamp without time zone N/A             YES
db_updated                timestamp without time zone N/A             YES
downloaded                boolean              N/A             YES
processed                 boolean              N/A             YES
meta                      jsonb                N/A             YES
md5                       text                 N/A             YES
s3_added                  timestamp without time zone N/A             YES
gdrive_added              timestamp without time zone N/A             YES