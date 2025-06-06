from fastapi import (
 BackgroundTasks, 
 File, 
 FastAPI,
 UploadFile,
 HTTPException,
 Form,  
 status, 
)
import logging
from pydantic import BaseModel, Json
from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Body,
)
from fastapi.responses import StreamingResponse,JSONResponse
from pydantic import (
    BaseModel,
    Field,
    ValidationError
)
from typing import (List,Optional)
from typing_extensions import (
    Annotated,
    Literal
)
from logging import Logger

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from models import (
     CompleteQryModel,
     GenAiCortexAudit,
     Txt2SqlModel,
     AgentModel,
     SqlExecModel,
     SearchModel,
     AnalystModel,
     LoadVectorModel,
     UploadFileModel,
     PromptModel,
     PromptResponse,
     FrequentQuestionModel,
     FrequentQuestionResponse
)
from prompts import (
    get_conv_response,
)
from config import GenAiEnvSettings
from dependencies import (
    get_config,
    get_logger,
    get_load_timestamp,
    ValidApiKey,
    SnowFlakeConnector,
    log_response,
    update_log_response,
    get_cortex_search_details,
    get_cortex_analyst_details,
    get_load_vector_data
)
#from ReduceReuseRecycleGENAI.api import get_api_key
#from ReduceReuseRecycleGENAI.snowflake import snowflake_conn

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client
import httpx
import json
import uuid
import re
from functools import partial
from upload_your_data import read_file_extract
route = APIRouter(
    prefix="/api/cortex"
)
from   snowflake.connector.errors import DatabaseError
from datetime import datetime, date


@route.post("/complete")
async def llm_gateway(
        query: Annotated[CompleteQryModel,Body(embed=True)], 
        config: Annotated[GenAiEnvSettings,Depends(get_config)],
        logger: Annotated[Logger,Depends(get_logger)],
        background_tasks: BackgroundTasks,
        get_load_datetime: Annotated[datetime,Depends(get_load_timestamp)]

):
    prompt = query.prompt.messages[-1].content
    messages_json = query.prompt.messages
    
    #The API key validation and generation has been pushed to backend; the api_validator will return True if API key is valid for the application.
    api_validator = ValidApiKey()
    try :
        if api_validator(query.api_key,query.aplctn_cd,query.app_id):
            try: 
                sf_conn = SnowFlakeConnector.get_conn(
                    query.aplctn_cd,
                    query.app_lvl_prefix,
                    query.session_id,
                )
            except DatabaseError as e: 
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not authorized to resources"
                )
            clnt = httpx.AsyncClient(verify=False)
            
            request_body = {
                "model": query.model,
                "messages": [
                    {
                        "role": "user",
                        "content": query.sys_msg + get_conv_response(messages_json, query.limit_convs) + prompt
                    }
                ]
            }

            headers = {
                "Authorization": f'Snowflake Token="{sf_conn.rest.token}"',
                "Content-Type": "application/json",
                "Accept": "application/json",
                "method":"cortex",
                "api_key":query.api_key
            }

            url = getattr(config.COMPLETE, "{}_host".format(config.env))
            response_text = []
            query_id = [None]
            fdbck_id = [str(uuid.uuid4())]
            
            async def data_streamer():
                """
                Stream data from the service and yield responses with proper exception handling.
                """
                try:
                    async with clnt.stream('POST', url, headers=headers, json=request_body) as response:
                        if response.is_client_error:
                            error_message = await response.aread()
                            raise HTTPException(
                                status_code=response.status_code,
                                detail=error_message.decode("utf-8")
                            )
                        if response.is_server_error:
                            error_message = await response.aread()
                            raise HTTPException(
                                status_code=response.status_code,
                                detail=error_message.decode("utf-8")
                            )

                        # Stream the response content
                        async for result_chunk in response.aiter_bytes():
                            for elem in result_chunk.split(b'\n\n'):
                                if b'content' in elem:  # Check for data presence
                                    try:
                                        chunk_dict = json.loads(elem.replace(b'data: ', b''))
                                        print(chunk_dict)
                                        full_response = chunk_dict['choices'][0]['delta']['text']
                                        full_response = full_response 
                                        response_text.append(full_response)
                                        yield full_response#result_chunk
                                        query_id[0] =  chunk_dict['id']
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Error decoding JSON: {e}")
                                        yield json.dumps({"error": "Error decoding JSON", "detail": str(e)})
                                        continue
                        yield "end_of_stream"
                        responses = {
                    "prompt":prompt,
                    "query_id": query_id[0],
                    "fdbck_id": fdbck_id[0] }
                    full_final_response = "".join(response_text)
                    yield json.dumps(responses)

                except httpx.RequestError as e:
                    logger.error(f"Request error: {e}")
                    yield json.dumps({"detail": str(e)})
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    yield json.dumps({"detail": str(e)})
            
                #Model recreated the for the Audit record
                audit_rec = GenAiCortexAudit(
                    edl_load_dtm = get_load_datetime,
                    edl_run_id = "0000",
                    edl_scrty_lvl_cd = "NA",
                    edl_lob_cd = "NA",
                    srvc_type = "complete",
                    aplctn_cd = config.pltfrm_aplctn_cd,
                    user_id = "Complete_User",#query.user_id,
                    mdl_id = query.model,
                    cnvrstn_chat_lmt_txt = query.limit_convs,
                    sesn_id = query.session_id,
                    prmpt_txt = prompt.replace("'","\\'"),
                    tkn_cnt = "0",
                    feedbk_actn_txt = "",
                    feedbk_cmnt_txt = "",
                    feedbk_updt_dtm = get_load_datetime,
                )
                background_tasks.add_task(log_response,audit_rec,query_id,str(full_final_response),fdbck_id,query.session_id)
            return StreamingResponse(data_streamer(),media_type='text/event-stream')
        else: 
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthenticated user"
            )
    
    except HTTPException as e:
        logger.error(f"Request error: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )

    
@route.post("/search_details/")
async def get_search_details(
        search_input: Annotated[List,Depends(SearchModel)]):
    try:
        return get_cortex_search_details(search_input) 
    except Exception as e: 
        raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized for search resources"
            ) 

@route.post("/analyst_details/")
async def get_analyst_details(
        analyst_input: Annotated[List,Depends(AnalystModel)]):
    try:
        return get_cortex_analyst_details(analyst_input)
    except HTTPException as he: 
        raise he


@route.post("/txt2sql")
async def llm_gateway(
        query: Annotated[Txt2SqlModel,Body(embed=True)], 
        config: Annotated[GenAiEnvSettings,Depends(get_config)],
        logger: Annotated[Logger,Depends(get_logger)],
        background_tasks: BackgroundTasks,
        get_load_datetime: Annotated[datetime,Depends(get_load_timestamp)]
):
    prompt = query.prompt.messages[-1].content
    #semantic_model = [f"{query.database_nm}.{query.schema_nm}." + item for item in query.semantic_model]
    
    #The API key validation and generation has been pushed to backend; the api_validator will return True if API key is valid for the application.
    api_validator = ValidApiKey()
    try:
        if api_validator(query.api_key,query.aplctn_cd,query.app_id):
            
            try: 
                sf_conn = SnowFlakeConnector.get_conn(
                    query.aplctn_cd,
                    query.app_lvl_prefix,
                    query.session_id
                )
            except DatabaseError as e: 
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not authorized to resources"
                )
            
            cs = sf_conn.cursor()

            stage_show = f"SHOW STAGES in SCHEMA {query.database_nm}.{query.schema_nm};"
            # Get list of all stage names
            df_stg_lst = cs.execute(stage_show).fetchall()
            stage_names  = [sublist[1] for sublist in df_stg_lst]
            print(stage_names)
            semantic_models = []

            for stage_name in stage_names:
                list_query = f"LIST @{query.database_nm}.{query.schema_nm}.{stage_name};"
                try:
                    df_stg_files_lst = cs.execute(list_query).fetchall()
                except Exception as e:
                    print(f"Error listing files in stage {stage_name}: {e}")
                    continue
                # Extract .yaml files
                for sublist in df_stg_files_lst:
                    file_path = sublist[0]
                    if file_path.endswith('.yaml') or file_path.endswith('.yaml.gz'):
                        semantic_models.append(file_path)
                print(semantic_models)

            #query1 = {"semantic_model": ["test.yaml", "contract_star_rating_v2.yaml"]}
            query1 = {"semantic_model": query.semantic_model}

            # Construct full stage paths for the query models
            semantic_model_paths = []
            for model_name in query1["semantic_model"]:
                # Find the matching path from semantic_models
                matching_paths = [path for path in semantic_models if path.endswith("/" + model_name) or path.endswith("/" + model_name + '.gz')]          
                if matching_paths:
                    # Use the first matching path and construct the full stage path
                    stage_path = f"@{query.database_nm}.{query.schema_nm}." + matching_paths[0]
                    semantic_model_paths.append(stage_path)
                else:
                    print(f"Warning: No matching path found for {model_name}")
                    raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No matching path found for {model_name}"
                    )
            #semantic_model_old = ["@DOC_AI_DB.HEDIS_SCHEMA.HEDIS_STAGE_FULL/" + item for item in query.semantic_model] 
            #print(semantic_model_old)
            semantic_model = semantic_model_paths  
            print("mdl", semantic_model)
            clnt = httpx.AsyncClient(verify=False,timeout=90.0)        
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                "semantic_model_file": semantic_model[0].split('.gz')[0] #f"@{query.database_nm}.{query.schema_nm}.{query.stage_nm}/{query.semantic_model[0]}",
            }
            headers = {
                "Authorization": f'Snowflake Token="{sf_conn.rest.token}"',
                "Content-Type": "application/json",
                "Accept": "application/json",
                "method":"cortex",
                "api_key":query.api_key
            }
            url = getattr(config.TXT2SQL, "{}_host".format(config.env))
            get_sql = ""
            query_id = [None]
            fdbck_id = [str(uuid.uuid4())]
            async def txt2sql_data_streamer():
                try:
                    """
                    Stream data from the TXT2SQL service and yield responses.
                    """
                    async with clnt.stream('POST', url, headers=headers, json=request_body) as response:
                        if response.is_client_error:
                            error_message = await response.aread()
                            raise HTTPException(
                                status_code=response.status_code,
                                detail=error_message.decode("utf-8")
                            )
                        if response.is_server_error:
                            error_message = await response.aread()
                            raise HTTPException(
                                status_code=response.status_code,
                                detail=error_message.decode("utf-8")
                            )
                        async for result_chunk in response.aiter_bytes():
                            #print(result_chunk)
                            for elem in result_chunk.split(b'\n\n'):
                                if b'content' in elem:  # Check for data presence
                                    try:
                                        chunk_dict = json.loads(elem.replace(b'data: ', b''))
                                        query_id[0]=chunk_dict['request_id']
                                        items = chunk_dict.get("message", {}).get("content", [])
                                        for item in items:
                                            item_type = item.get("type")
                                            if item_type == "text":
                                                yield item.get("text", "")
                                                yield "end_of_interpretation"
                                            elif item_type == "sql":
                                                get_sql = item.get("statement", "")
                                                #print("sql is ", get_sql)
                                                yield item.get("statement", "")
                                            elif item_type == "suggestions":
                                                yield json.dumps({"suggestions": item.get("suggestions", [])})
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Error decoding JSON: {e}")
                                        continue
                        yield "end_of_stream"
                        responses = {
                        "prompt":prompt,
                        "query_id": query_id[0],
                        "fdbck_id": fdbck_id[0],
                        "type": "sql" }
                        full_final_response = "".join(get_sql)
                        yield json.dumps(responses)
                        #yield json.dumps({"type": "sql"})
                        #yield json.dumps({"prompt":prompt,"type": "sql"})

                except httpx.RequestError as e:
                    logger.error(f"Request error: {e}")
                    yield json.dumps({"detail": str(e)})
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    yield json.dumps({"detail": str(e)})

                #Model recreated the for the Audit record
                audit_rec = GenAiCortexAudit(
                    edl_load_dtm = get_load_datetime,
                    edl_run_id = "0000",
                    edl_scrty_lvl_cd = "NA",
                    edl_lob_cd = "NA",
                    srvc_type = "Analyst",
                    aplctn_cd = config.pltfrm_aplctn_cd,
                    user_id = "Analyst_User",#query.user_id,
                    mdl_id = query.model,
                    cnvrstn_chat_lmt_txt = "0",#query.cnvrstn_chat_lmt_txt,
                    sesn_id = query.session_id,
                    prmpt_txt = prompt.replace("'","\\'"),
                    tkn_cnt = "0",
                    feedbk_actn_txt = "",
                    feedbk_cmnt_txt = "",
                    feedbk_updt_dtm = get_load_datetime,
                )
                background_tasks.add_task(log_response,audit_rec,query_id,str(full_final_response),fdbck_id,query.session_id)

            # Return a streaming response
            return StreamingResponse(txt2sql_data_streamer(), media_type='text/event-stream')
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthenticated user"
            ) 
    except HTTPException as e:
        logger.error(f"Request error: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


@route.post("/agent")
async def llm_gateway(
        query: Annotated[AgentModel,Body(embed=True)], 
        config: Annotated[GenAiEnvSettings,Depends(get_config)],
        logger: Annotated[Logger,Depends(get_logger)],
        background_tasks: BackgroundTasks,
        get_load_datetime: Annotated[datetime,Depends(get_load_timestamp)]

):
    prompt = query.prompt.messages[-1].content
    search_service = [f"{query.database_nm}.{query.schema_nm}." + item for item in query.search_service]

    api_validator = ValidApiKey()
    try:
        if api_validator(query.api_key,query.aplctn_cd,query.app_id):   
            try: 
                sf_conn = SnowFlakeConnector.get_conn(
                    query.aplctn_cd,
                    query.app_lvl_prefix,
                    query.session_id
                )
            except DatabaseError as e: 
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not authorized to resources"
                )
            cs = sf_conn.cursor()

            stage_show = f"SHOW STAGES in SCHEMA {query.database_nm}.{query.schema_nm};"
            # Get list of all stage names
            df_stg_lst = cs.execute(stage_show).fetchall()
            stage_names  = [sublist[1] for sublist in df_stg_lst]
            print(stage_names)
            semantic_models = []

            for stage_name in stage_names:
                list_query = f"LIST @{query.database_nm}.{query.schema_nm}.{stage_name};"
                try:
                    df_stg_files_lst = cs.execute(list_query).fetchall()
                except Exception as e:
                    print(f"Error listing files in stage {stage_name}: {e}")
                    continue
                # Extract .yaml files
                for sublist in df_stg_files_lst:
                    file_path = sublist[0]
                    if file_path.endswith('.yaml'):
                        semantic_models.append(file_path)
                print(semantic_models)

            #query1 = {"semantic_model": ["test.yaml", "contract_star_rating_v2.yaml"]}
            query1 = {"semantic_model": query.semantic_model}

            # Construct full stage paths for the query models
            semantic_model_paths = []
            for model_name in query1["semantic_model"]:
                # Find the matching path from semantic_models
                matching_paths = [path for path in semantic_models if path.endswith("/" + model_name)]          
                if matching_paths:
                    # Use the first matching path and construct the full stage path
                    stage_path = f"@{query.database_nm}.{query.schema_nm}." + matching_paths[0]
                    semantic_model_paths.append(stage_path)
                else:
                    print(f"Warning: No matching path found for {model_name}")
            #semantic_model_old = ["@DOC_AI_DB.HEDIS_SCHEMA.HEDIS_STAGE_FULL/" + item for item in query.semantic_model] 
            #print(semantic_model_old)
            semantic_model = semantic_model_paths  
            print(semantic_model)
            clnt = httpx.AsyncClient(verify=False,timeout=150.0)
            request_body = {
                "model": query.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                "tools": [],
                "tool_resources": {}
            }
            #{ "tool_spec": { "type": "sql_exec", "name": "sql_exec" } },{ "tool_spec": { "type": "data_to_chart", "name": "data_to_chart" } }
            # Dynamically append cortex_analyst_text_to_sql tools and tool_resources
            for idx, semantic_model_files in enumerate(semantic_model, start=1):
                tool_name = f"analyst{idx}"
                # Append to tools
                request_body["tools"].append({
                    "tool_spec": {
                        "type": "cortex_analyst_text_to_sql",
                        "name": tool_name
                    }
                })
                # Append to tool_resources
                request_body["tool_resources"][tool_name] = {
                    "semantic_model_file": semantic_model_files  # Each tool references its own list of .yaml files
                }

            # Dynamically append cortex_search tools and tool_resources
            for idx, service in enumerate(search_service, start=1):
                tool_name = f"search{idx}"
                # Append to tools
                request_body["tools"].append({
                    "tool_spec": {
                        "type": "cortex_search",
                        "name": tool_name
                    }
                })
                # Append to tool_resources
                request_body["tool_resources"][tool_name] = {
                    "name": service,  # Each tool references one service
                    "max_results": query.search_limit
                }
            headers = {
                "Authorization": f'Snowflake Token="{sf_conn.rest.token}"',
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            print(request_body)
            url = getattr(config.AGENT, "{}_host".format(config.env))    
            query_id = [None]
            fdbck_id = [str(uuid.uuid4())]
            full_response_text = []
            full_sql_response = []        
            import re
            async def agent_data_streamer():
                citations = []
                async with clnt.stream('POST', url, headers=headers, json=request_body) as response:
                    if response.is_client_error:
                        error_message = await response.aread()
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=error_message.decode("utf-8")
                        )
                    if response.is_server_error:
                        error_message = await response.aread()
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=error_message.decode("utf-8")
                        )
                    async for result_chunk in response.aiter_bytes():
                        #print(result_chunk)
                        for elem in result_chunk.split(b'\n\n'):
                            print("ele",elem)
                            if b'data:' not in elem:
                                continue
                            try:
                                match = re.search(rb'data: ({.*})', elem)
                                if not match:
                                    continue
                                #print(match.group(1))
                                chunk_dict = json.loads(match.group(1))
                                #print(chunk_dict)
                                query_id[0]=chunk_dict.get("id", {})
                                delta = chunk_dict.get('delta', {})
                                content_list = delta.get('content', [])
                                for content_item in content_list:
                                    content_type = content_item.get("type")
                                    if content_type == "text":
                                        text_part = content_item.get("text", "")
                                        full_response_text.append(text_part)
                                        response = text_part.replace("【†", "[").replace("†】", "]").replace("】", "]").replace("【", "[")
                                        yield response
                                    elif content_type == "tool_results":
                                        tool_results = content_item.get("tool_results", {})
                                        content_list_inner = tool_results.get("content", [])
                                        for result in content_list_inner:
                                            if result.get("type") == "json":
                                                json_obj = result.get("json", {})
                                                citations = json_obj.get('searchResults', [])
                                                #print("sea",citations)
                                                extracted_text = json_obj.get("text", "")
                                                if extracted_text:
                                                    full_response_text.append(extracted_text)
                                                    yield extracted_text
                                                    yield "end_of_interpretation \n  "
                                                extracted_sql = json_obj.get("sql", "")
                                                if extracted_sql:
                                                    full_sql_response.append(extracted_sql)
                                                    yield extracted_sql
                                    elif content_type == "tool_use":
                                        continue  # Optional: capture or log tool_use
                            except json.JSONDecodeError:
                                continue
                    yield "end_of_stream"
                    if citations:
                        yield json.dumps({"citations": citations})
                    if full_response_text and full_sql_response: 
                        final_response = extracted_sql
                        yield json.dumps({"prompt":prompt,"query_id": query_id[0],
                            "fdbck_id": fdbck_id[0],"type": "sql"})
                        #yield json.dumps({"type": "sql"})
                    elif full_response_text:  # Check if there's any text to yield
                        final_response = "".join(full_response_text)
                        yield json.dumps({"prompt":prompt,"query_id": query_id[0],
                            "fdbck_id": fdbck_id[0],"type": "text"})
        
                #Model recreated the for the Audit record
                audit_rec = GenAiCortexAudit(
                    edl_load_dtm = get_load_datetime,
                    edl_run_id = "0000",
                    edl_scrty_lvl_cd = "NA",
                    edl_lob_cd = "NA",
                    srvc_type = "Agent",
                    aplctn_cd = config.pltfrm_aplctn_cd,
                    user_id = "Agent_user",#query.user_id,
                    mdl_id = query.model,
                    cnvrstn_chat_lmt_txt = "0",#query.cnvrstn_chat_lmt_txt,
                    sesn_id = query.session_id,
                    prmpt_txt = prompt.replace("'","\\'"),
                    tkn_cnt = "0",
                    feedbk_actn_txt = "",
                    feedbk_cmnt_txt = "",
                    feedbk_updt_dtm = get_load_datetime,
                )
                background_tasks.add_task(log_response,audit_rec,query_id,str(final_response),fdbck_id,query.session_id)

            return StreamingResponse(agent_data_streamer(), media_type='text/event-stream')
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthenticated user"
            ) 
    except HTTPException as e:
        logger.error(f"Request error: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


@route.post("/txt2sql/run_sql_query")
async def run_sql_query(
    query: Annotated[SqlExecModel, Body(embed=True)],
    config: Annotated[GenAiEnvSettings, Depends(get_config)],
    logger: Annotated[Logger, Depends(get_logger)],
    background_tasks: BackgroundTasks
):
    """
    Execute an SQL query in Snowflake and return the results as JSON.
    """
    api_validator = ValidApiKey()
    if api_validator(query.api_key, query.aplctn_cd, query.app_id):
        try:
            # Establish Snowflake connection
            sf_conn = SnowFlakeConnector.get_conn(
                query.aplctn_cd,
                query.app_lvl_prefix,
                query.session_id
            )
        except DatabaseError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to resources"
            )

        try:
            # Execute the SQL query
            cs = sf_conn.cursor()
            cs.execute(query.exec_sql)

            # Fetch the results into a DataFrame
            df = cs.fetch_pandas_all()
            df = df.fillna(0)  # Replace NaN values with 0

            # Convert date and datetime objects to strings
            for column in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
                df[column] = df[column].dt.strftime('%Y-%m-%d %H:%M:%S')  # Format datetime
            for column in df.select_dtypes(include=["object"]).columns:
                df[column] = df[column].apply(lambda x: x.isoformat() if isinstance(x, (datetime, date)) else x)

            cs.close()

            # Convert DataFrame to JSON
            result_json = df.to_dict(orient="records")
            return JSONResponse(content=result_json)

        except Exception as e:
            logger.error(f"Error executing SQL query: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while executing the SQL query."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated user"
        )

@route.post("/update_feedback/")
async def update_feedback(
    fdbck_id: str,
    session_id: Optional[str],
    feedbk_actn_txt: Optional[str] = None,
    feedbk_cmnt_txt: Optional[str] = None
):
    """
    Update feedback in the audit table and return a success message once the update is complete.
    """
    try:
        # Call the update_log_response function directly
        result = update_log_response(fdbck_id, feedbk_actn_txt, feedbk_cmnt_txt, session_id)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating feedback: {str(e)}"
        )

@route.post("/upload_file/")
async def upload_file(
    query: Annotated[str, Form()],
    config: Annotated[GenAiEnvSettings, Depends(get_config)],
    logger: Annotated[Logger, Depends(get_logger)],
    files: List[UploadFile]
):
    """Upload and process multiple CSV, PDF, DOCX, or TXT files."""
    query = json.loads(query)
    api_validator = ValidApiKey()
    if api_validator(query['api_key'], query['aplctn_cd'], query['app_id']):
        sf_conn = SnowFlakeConnector.get_conn(
            query['aplctn_cd'],
            query['app_lvl_prefix'],
            query['session_id'],
        )
        res = await read_file_extract(files,sf_conn,app_nm=query['app_nm'])
        return res
    else: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated user"
        )
# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@route.get("/prompts/{aplctn_cd}")
async def get_prompts(aplctn_cd: str):
    try:
        async with sse_client("http://<EC2-IP>:8001/sse") as connection:
            async with ClientSession(*connection) as session:
                await session.initialize()
                result = await session.read_resource(f"genaiplatform://{aplctn_cd}/prompts/hedis-prompt")

                # ✅ Extract prompts from result["contents"][0]["text"]
                contents = result.get("contents", [])
                if contents and "text" in contents[0]:
                    return contents[0]["text"]
                else:
                    return []  # no prompts found
    except HTTPException as e:
        logger.error(f"Request error in get_prompts: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in get_prompts: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@route.get("/frequent_questions/{aplctn_cd}")
async def get_frequent_questions(aplctn_cd: str):
    try:
        async with sse_client("http://localhost:8000/sse") as connection:
            async with ClientSession(*connection) as session:
                await session.initialize()
                result = await session.read_resource(f"genaiplatform://{aplctn_cd}/frequent_questions/hedis-question")
                return result
    except HTTPException as e:
        logger.error(f"Request error in get_frequent_questions: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in get_frequent_questions: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@route.post("/add_prompt")
async def add_prompt(data: PromptModel):
    try:
        async with sse_client("http://localhost:8000/sse") as connection:
            async with ClientSession(*connection) as session:
                await session.initialize()
                result = await session.call_tool(name="add-prompts", arguments={
                    "uri": data.uri,
                    "prompt": data.prompt
                })
                return result
    except HTTPException as e:
        logger.error(f"Request error in add_prompt: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in add_prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@route.post("/add_frequent_question")
async def add_frequent_question(data: FrequentQuestionModel):
    try:
        async with sse_client("http://localhost:8000/sse") as connection:
            async with ClientSession(*connection) as session:
                await session.initialize()
                result = await session.call_tool(name="add-frequent-questions", arguments={
                    "uri": data.uri,
                    "question": data.question
                })
                return result
    except HTTPException as e:
        logger.error(f"Request error in add_frequent_question: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in add_frequent_question: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


