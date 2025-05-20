from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any

class RepoCredentials(BaseModel):
    repo_url: HttpUrl
    username: Optional[str] = None # Username might not be needed if token is like a PAT
    password: Optional[str] = None # Could be a password or an access token

class RepoResponse(BaseModel):
    status: str  # "success" or "error"
    message: str
    repo_name: Optional[str] = None
    repo_path: Optional[str] = None
    error_details: Optional[str] = None

class ProjectTypeResponse(BaseModel):
    status: str  # "success" or "error"
    message: Optional[str] = None
    is_maven: Optional[bool] = None
    is_gradle: Optional[bool] = None
    is_spring_boot: Optional[bool] = None
    build_system: Optional[str] = None
    project_type: Optional[str] = None
    error_details: Optional[str] = None

class EndpointInfo(BaseModel):
    controller: str
    method: str
    http_method: str
    path: str

class EndpointResponse(BaseModel):
    status: str  # "success" or "error"
    message: Optional[str] = None
    endpoints: Optional[List[EndpointInfo]] = None
    error_details: Optional[str] = None 

class MethodParameter(BaseModel):
    type: str
    name: str

class MethodCall(BaseModel):
    class_name: str
    method: str
    class_type: Optional[str] = "unknown"
    # Recursive references for nested calls
    calls: Optional[List['MethodCall']] = None

# Important: this is needed for the recursive model
MethodCall.update_forward_refs()

class FlowEntry(BaseModel):
    class_name: str
    class_type: str
    method: str
    parameters: Optional[List[MethodParameter]] = None
    return_type: str
    calls: Optional[List[MethodCall]] = None

class EndpointFlow(BaseModel):
    controller: str
    endpoint: str
    http_method: str
    flow: List[FlowEntry]

class FlowResponse(BaseModel):
    status: str  # "success" or "error"
    message: Optional[str] = None
    flows: Optional[List[EndpointFlow]] = None
    error_details: Optional[str] = None 