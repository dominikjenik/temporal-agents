temporal. zadefinujme manazera - potrebujeme aby z poz8adacky pouzivatela extrahoval intent teda zamer, to bude rozhodovat o nasom flowe dalej,  zadefinujme prvy intent - project_status - ak sa koncovy uzivatel opyta "co na praci/co je nove/aku mame robotu". tento intent LLM managera vyparsuje ako JSON {intent:"project_status"}. Nasledne ho spracovava v tomto pripade temporal a namiesto dalsieho volania LLM v tomto pripade len vypise z tabulky tasks usporiadany zoznam podla priority projektu. Dva testy - prvy pokryva prvu cast - LLM, druhy pokryva temporal volanie DB.

| test_parse_intent_returns_project_status[co na praci-project_status]
| test_parse_intent_returns_project_status[co je nove-project_status]
| test_parse_intent_returns_project_status[aku mame robotu-project_status]
| test_parse_intent_returns_project_status[what tasks do we have-project_status]
| test_project_status_queries_db_and_formats
| test_format_tasks_groups_by_project
| test_format_tasks_empty
| TestDBQueryModelDefaults::test_dbquery_model_defaults
| TestStoreTask::test_store_regular_task
| TestStoreTask::test_store_hitl_task
| TestStoreTask::test_store_task_default_priority
| TestListTasks::test_list_tasks_returns_pending_only
| TestListTasks::test_list_tasks_sorted_by_priority
| TestListTasks::test_list_tasks_hitl_and_task_together
| TestExecuteDbQuery::test_unknown_table_raises
| TestExecuteDbQuery::test_query_tasks_table
| TestExecuteDbQuery::test_query_with_filter
| TestStoreTaskOptions::test_store_task_options_timeout
| TestExecuteDbQueryOptions::test_execute_db_query_options_timeout