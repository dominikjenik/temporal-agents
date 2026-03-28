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
| test_extract_intent_parses_llm_output[{"intent": "project_status"}-project_status]
| test_extract_intent_parses_llm_output[```json\n{"intent": "project_status"}\n```-project_status]
| test_extract_intent_parses_llm_output[{"intent": "unknown"}-unknown]
| test_extract_intent_parses_llm_output[some garbage output-unknown]
| test_extract_intent_parses_llm_output[Sure! {"intent": "project_status"} here you go-project_status]
nova poziadavka: new_feature intent → projektak agent → HITL do DB → confirm signal → resolved. UI: task list (polling 1s, HITL bliká), detail panel s OK / Komentovať buttonmi.
upresnenie: (1) ManagerWorkflow vracia "Požiadavka odoslaná projektovému manažérovi." (2) ProjectakWorkflow vracia JSON {intent:"duplicate", payload:"..."} — rovnaký formát ako manager. (3) kontext window: v detail paneli prebieha konverzácia priamo s projektakom cez comment signal + get_comments query; Komentovať button posiela komentár, odpoveď sa zobrazí v chate.
| test_projektak_confirm_returns_duplicate_json
| test_projektak_stores_hitl_and_updates_status
| test_projektak_handles_comment_then_confirm
| test_manager_routes_new_feature
nova poziadavka: format check a learning loop. (1) Ak manager alebo projektak nevrátia odpoveď v očakávanom formáte (intent=unknown), Temporal workflow automaticky volá capture_lesson aktivitu — vznikne learning request pre daný projekt. (2) capture_lesson zapisuje do DB tabuľky tasks (project=temporal, type=lesson, status=pending) — nie do súboru. Používateľ systému vidí lesson v task liste a môže sa rozhodnúť kedy ju adresovať. (3) Model manažérskych agentov je definovaný v frontmatter agent súboru (agents/manager.md: model: claude-haiku-4-5-20251001), nie ako OS premenná — model je súčasť definície agenta a platí dlhodobo. (4) retry_policy maximum_attempts=1 pre všetky aktivity v ManagerWorkflow a ProjectakWorkflow — zabraňuje zacykleniu pri chybách počas debugovania.
| test_unknown_intent_triggers_capture_lesson
| TestCaptureLessonWritesToDB::test_inserts_lesson_row
| TestCaptureLessonHeartbeat::test_heartbeat_called
| TestCaptureLessonOutcomeInTitle::test_outcome_in_title[success]
| TestCaptureLessonOutcomeInTitle::test_outcome_in_title[failure]
nova poziadavka: end-to-end pipeline — vstup "nova feature temporal projektu - pridaj UI button ok" musí prejsť celým reťazcom: Manager resolvne intent new_feature, spustí ProjectakWorkflow ako child (ABANDON), Projektak zapíše HITL task do DB a čaká na confirm signál (stav waiting_hitl). Timeout pri skutočnom LLM volaní bol dôvodom zlyhania — pokryté unit testom s mocknutým parse_intent.
| test_new_feature_message_full_pipeline
nova poziadavka: UI — dve opravy. (1) TaskDetail zobrazoval "Načítavam posúdenie..." donekonečna pre úlohy bez workflow_id — opravené kontrolou !task.workflow_id → zobrazí "Posúdenie nedostupné.". (2) Nadpis v TaskDetail bol zakrytý pevnou NavBar — opravené: backdrop zmenil items-center na items-start pt-20, modal dostane max-h-[calc(100vh-6rem)].
| App > TaskDetail — task without workflow_id > shows "Posúdenie nedostupné." and not "Načítavam posúdenie..."
| App > TaskDetail — task with workflow_id > shows "Načítavam posúdenie..." while result is null
| App > TaskDetail — modal title visibility > backdrop has items-start and pt-20 so title is not hidden behind NavBar
nova poziadavka: UI — "Načítavam posúdenie..." nesmie byť prázdne — má zobrazovať log z celého workflow. ProjectakWorkflow akumuluje log záznamy počas behu (prijatá požiadavka, posúdenie, zápis do DB, čakanie, potvrdenie, komentáre) a exponuje ich cez get_log query. API /hitl/{workflow_id}/state vracia log pole. UI zobrazuje log ako kompaktný terminálový výpis; "Načítavam posúdenie..." sa zobrazí iba ak log je ešte prázdny. Po príchode result bannera je log stále viditeľný ako kontext.
| test_projektak_log_contains_key_steps
