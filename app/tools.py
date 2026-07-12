from app import crm

TOOLS = {} #name -> function (the phone book)

def tool(fn):
    #Register a function so an agent can call it by name
    TOOLS[fn.__name__]=fn
    return fn

@tool
def crm_lookup(email: str) -> dict|None:
    #Look up a customer by email. Returns their record or None
    return crm.lookup(email)

def run_tool(name:str,  args:dict) -> str:
    #Dial a tool by name with its args; return the result as text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR:unknown tool {name!r}"

    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"

