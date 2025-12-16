"""
Azure LLM Provider for LangChain integration.

This module provides a centralized way to manage Azure LLM and embedding services
using LangChain's AzureChatOpenAI and AzureOpenAIEmbeddings.
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential

# LangChain imports
from langchain_openai.chat_models import AzureChatOpenAI
from langchain_openai.embeddings import AzureOpenAIEmbeddings

# Configure logging
logger = logging.getLogger(__name__)


class AzureLLMProvider:
    """
    Provider for Azure LLM and embedding services using LangChain.

    This class manages authentication and configuration for Azure OpenAI services
    used in the application.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        app_id: Optional[str] = None,
        secret: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        api_version: Optional[str] = None,
        user_id: Optional[str] = None,
        api_version_embedder: Optional[str] = None
    ):
        """
        Initialize the Azure LLM Provider.

        Args:
            tenant_id: Azure tenant ID (defaults to env var AZURE_TENANT_ID)
            app_id: Azure application ID (defaults to env var AZURE_APP_ID)
            secret: Azure client secret (defaults to env var AZURE_CLIENT_SECRET)
            openai_api_base: Azure API base URL (defaults to env var AZURE_API_BASE)
            llm_model: LLM model name (defaults to env var AZURE_LLM_MODEL)
            embedding_model: Embedding model name (defaults to env var AZURE_EMBEDDING_MODEL)
            api_version: API version (defaults to env var AZURE_API_VERSION)
            user_id: User ID for headers (defaults to env var AZURE_USER_ID)
            api_version_embedder: API version for embeddings (defaults to env var AZURE_EMBEDDING_VERSION)
        Raises:
            ValueError: If required environment variables are not set
        """
        # Load environment variables
        load_dotenv()
        # Fallback: search for .env in current and up to 5 parent directories to cover different layouts
        try:
            from pathlib import Path
            base = Path.cwd()
            for _ in range(6):
                candidate = base / ".env"
                if candidate.exists():
                    load_dotenv(dotenv_path=str(candidate), override=True)
                base = base.parent
        except Exception:
            pass

        logging.info("CONFIGURANDO LLM")
        logging.info("AZURE_TENANT_ID: " + os.getenv("AZURE_TENANT_ID"))
        logging.info("AZURE_APP_ID: " + os.getenv("AZURE_APP_ID"))
        logging.info("AZURE_CLIENT_SECRET: " + os.getenv("AZURE_CLIENT_SECRET"))

        # Initialize configuration
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.app_id = app_id or os.getenv("AZURE_APP_ID")
        self.secret = secret or os.getenv("AZURE_CLIENT_SECRET")
        self.openai_api_base = openai_api_base or os.getenv("AZURE_API_BASE")
        self.llm_model = llm_model or os.getenv("AZURE_LLM_MODEL")
        self.embedding_model = embedding_model or os.getenv("AZURE_EMBEDDING_MODEL")
        self.api_version = api_version or os.getenv("AZURE_API_VERSION")
        self.user_id = user_id or os.getenv("AZURE_USER_ID")
        self.api_version_embedder = api_version_embedder or os.getenv("AZURE_EMBEDDING_VERSION")
 
        # Config availability flag (non-fatal; degrades gracefully if not fully configured)
        self.configured = True
        required_map = {
            "AZURE_TENANT_ID": self.tenant_id,
            "AZURE_APP_ID": self.app_id,
            "AZURE_CLIENT_SECRET": self.secret,
            "AZURE_API_BASE": self.openai_api_base,
            "AZURE_LLM_MODEL": self.llm_model,
            "AZURE_EMBEDDING_MODEL": self.embedding_model,
            "AZURE_API_VERSION": self.api_version,
            "AZURE_USER_ID": self.user_id
        }
        missing = [k for k, v in required_map.items() if not v]
        if missing:
            logger.warning(f"Azure LLM provider not fully configured. Missing: {', '.join(missing)}")
            self.configured = False

        # Validate configuration
        self._validate_configuration()

        # Initialize cached LLM
        self._llm: Optional[AzureChatOpenAI] = None

        logger.info("Azure LLM Provider initialized successfully")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_configuration(self) -> None:
        """
        Validate that all required configuration values are present.

        Raises:
            ValueError: If any required configuration is missing
        """
        # If not fully configured, skip hard failure to allow graceful degradation
        if not getattr(self, "configured", True):
            logger.warning("Azure LLM provider not fully configured. Skipping strict validation.")
            return

        required_configs = {
            "AZURE_TENANT_ID": self.tenant_id,
            "AZURE_APP_ID": self.app_id,
            "AZURE_CLIENT_SECRET": self.secret,
            "AZURE_API_BASE": self.openai_api_base,
            "AZURE_LLM_MODEL": self.llm_model,
            "AZURE_EMBEDDING_MODEL": self.embedding_model,
            "AZURE_API_VERSION": self.api_version,
            "AZURE_USER_ID": self.user_id
        }

        missing = [k for k, v in required_configs.items() if not v]
        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    # -------------------------------------------------------------------------
    # Token generation
    # -------------------------------------------------------------------------

    def generate_bearer_token(self) -> str:
        """
        Generate a bearer token for Azure authentication.

        Returns:
            Bearer token string
        """
        try:
            credential = ClientSecretCredential(self.tenant_id, self.app_id, self.secret)
            token_response = credential.get_token(
                "api://2f72c6d3-2d2e-4800-b458-1642e97f9dff/.default"
            )
            logger.debug("Bearer token generated successfully")
            return token_response.token
        except Exception as e:
            logger.error(f"Error generating bearer token: {e}")
            raise Exception(f"Error generating bearer token: {e}")

    # -------------------------------------------------------------------------
    # LLM Management
    # -------------------------------------------------------------------------

    def get_llm(self) -> Optional[AzureChatOpenAI]:
        """
        Get or create the AzureChatOpenAI LLM instance.

        Returns:
            Configured AzureChatOpenAI instance.
        """
        if self._llm is None:
            logger.info("Creating AzureChatOpenAI LLM instance...")
            extra_body = {"axet-user-id": self.user_id}
            
            def token_provider():
                return self.generate_bearer_token()
        
            self._llm = AzureChatOpenAI(
                azure_endpoint=self.openai_api_base,
                azure_deployment=self.llm_model,
                api_version=self.api_version,
                azure_ad_token_provider=token_provider,
                default_headers=extra_body,
                temperature=0.2,
            )
            logger.info("AzureChatOpenAI LLM instance created successfully.")

        return self._llm

    def refresh_token(self) -> None:
        """
        Refresh Azure AD token and reset LLM instance.
        """
        logger.info("Refreshing Azure AD token...")
        self._llm = None
        logger.info("Azure token refreshed successfully.")

    # -------------------------------------------------------------------------
    # Embeddings Management
    # -------------------------------------------------------------------------

    def get_embedder(self) -> AzureOpenAIEmbeddings:
        """
        Create an AzureOpenAIEmbeddings instance.

        Returns:
            Configured AzureOpenAIEmbeddings instance.
        """
        try:
            logger.info("Creating AzureOpenAIEmbeddings instance...")
            azure_ad_token = self.generate_bearer_token()
            extra_body = {"axet-user-id": self.user_id}

            embedder = AzureOpenAIEmbeddings(
                api_version=self.api_version_embedder or self.api_version,
                azure_endpoint=self.openai_api_base,
                azure_ad_token=azure_ad_token,
                model=self.embedding_model,
                default_headers=extra_body,
            )

            logger.info("AzureOpenAIEmbeddings instance created successfully.")
            return embedder

        except ImportError:
            logger.error(
                "langchain_openai not installed. Install with: pip install langchain-openai"
            )
            raise
        except Exception as e:
            logger.error(f"Error creating embedder: {e}")
            raise

    # -------------------------------------------------------------------------
    # Config helpers for external use
    # -------------------------------------------------------------------------

    def get_llm_config(self) -> Dict[str, Any]:
        """
        Return LLM configuration dictionary for external tools.

        Returns:
            Dict containing LangChain LLM reference and metadata.
        """
        llm = self.get_llm()
        config = {
            "provider": "custom",
            "config": {
                "llm": llm,
                "model_name": self.llm_model,
                "openai_api_base": self.openai_api_base,
                "api_version": self.api_version,
            },
        }
        logger.info("LLM configuration for LangChain prepared successfully.")
        return config

    def get_embedder_config(self) -> Dict[str, Any]:
        """
        Return embedder configuration dictionary for external tools.

        Returns:
            Dict containing LangChain embedder reference and metadata.
        """
        embedder = self.get_embedder()
        config = {
            "provider": "custom",
            "config": {
                "embedder": embedder,
                "model_name": self.embedding_model,
                "openai_api_base": self.openai_api_base,
                "api_version": self.api_version_embedder or self.api_version,
            },
        }
        logger.info("Embedder configuration for LangChain prepared successfully.")
        return config

    # -------------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Test connection to Azure services.

        Returns:
            True if successful, False otherwise.
        """
        try:
            token = self.generate_bearer_token()
            if not token:
                logger.error("Token generation failed.")
                return False

            llm = self.get_llm()
            if not llm:
                logger.error("LLM initialization failed.")
                return False

            embedder = self.get_embedder()
            if not embedder:
                logger.error("Embedder initialization failed.")
                return False

            logger.info("Azure connection test successful.")
            return True
        except Exception as e:
            logger.error(f"Azure connection test failed: {e}")
            return False


# -------------------------------------------------------------------------
# Global instance helpers
# -------------------------------------------------------------------------

_azure_provider: Optional[AzureLLMProvider] = None


def get_azure_provider() -> AzureLLMProvider:
    """
    Get or create the global Azure provider instance.

    Returns:
        AzureLLMProvider instance.
    """
    global _azure_provider
    if _azure_provider is None:
        _azure_provider = AzureLLMProvider()
    return _azure_provider


def set_azure_provider(provider: AzureLLMProvider) -> None:
    """
    Set the global Azure provider instance.

    Args:
        provider: AzureLLMProvider instance to set as global.
    """
    global _azure_provider
    _azure_provider = provider
