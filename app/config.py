from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    # Supabase configuration
    supabase_url: str = "https://uayheqlzfeanolsekutu.supabase.co"
    supabase_publishable_key: str =  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVheWhlcWx6ZmVhbm9sc2VrdXR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY3NTM4NDMsImV4cCI6MjEwMjMyOTg0M30.-YZ_Bw48VzAvTzdxCx4ANFD0EPvuj01i-fb_UyG6ReE"

    database_url: str ="postgresql://postgres.uayheqlzfeanolsekutu:tj0ZhNGmJduBOAXN@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"

    # Worker and sandbox configuration
    redis_url: str = "redis://localhost:6379/0"
    workspace_root: str = "/workspace/"  # one sub-folder per job
    answer_timeout: int = 3600  # seconds to wait for a human answer
    
    # API and model configuration
    api_key: str = 'v1.CmMKHHN0YXRpY2tleS1lMDByNnRuY2VoNnJwMXRnbXQSIXNlcnZpY2VhY2NvdW50LWUwMHQxa2pjeXA1NnJjYTlyZjIMCIPP4NYGEJuh27EBOgsI_NH4oQcQwILqDUACWgNlMDA.AAAAAAAAAAGSXDit5lWIVF4r-L08Knz9In6paCefVBJqg2zULp6tUnuq-AV9PDdfSbo6u7cMpLCBWq4MWhFneg1xXVk78ngK'
    base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    model_id: str = 'moonshotai/Kimi-K2.7-Code'

    #frontend redirect url
    frontend_redirect: str = ""
    frontend_callback: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()