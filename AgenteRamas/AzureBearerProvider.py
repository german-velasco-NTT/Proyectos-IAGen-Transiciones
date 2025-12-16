# AzureBearerProvider.py

from typing import Optional, Any, Union, List, Dict
import logging
import httpx
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class AzureEnablerSimple:
    """Cliente para Azure OpenAI Enabler de Axet."""

    def __init__(
        self,
        bearer_token: str,
        azure_endpoint: str,
        deployment_name: str,
        api_version: str = "2024-02-15-preview",
        temperature: float = 0.7,
        max_tokens: int = 16000,
        axet_user_id: Optional[str] = None,
        asset_id: Optional[str] = None,  # ⭐ NUEVO
    ):
        self.bearer_token = bearer_token
        self.azure_endpoint = azure_endpoint.rstrip('/')
        self.deployment_name = deployment_name
        self.api_version = api_version
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.axet_user_id = axet_user_id
        self.asset_id = asset_id  # ⭐ NUEVO

        self._client: Optional[AzureOpenAI] = None

        logger.info("AzureEnablerSimple initialized")
        logger.info(f"  Endpoint: {self.azure_endpoint}")
        logger.info(f"  Deployment: {deployment_name}")
        logger.info(f"  Axet User ID: {axet_user_id or 'NOT PROVIDED'}")
        logger.info(f"  Asset ID: {asset_id or 'NOT PROVIDED'}")

    def _build_default_headers(self) -> Dict[str, str]:
        """Headers por defecto para todas las peticiones (sin hardcodear)."""
        headers: Dict[str, str] = {}
        if self.axet_user_id:
            headers["axet-user-id"] = self.axet_user_id
        if self.asset_id:
            headers["axet-asset-id"] = self.asset_id  # ⭐ se envía como header
        return headers

    def update_headers(self, *, axet_user_id: Optional[str] = None, asset_id: Optional[str] = None) -> None:
        """
        Permite actualizar headers en caliente (opcional).
        Útil si quieres cambiar el asset-id sin recrear el cliente.
        """
        changed = False
        if axet_user_id is not None:
            self.axet_user_id = axet_user_id
            changed = True
        if asset_id is not None:
            self.asset_id = asset_id
            changed = True

        if changed and self._client is not None:
            # httpx.Client.headers es mutable: se actualiza el cliente existente
            try:
                http_client: httpx.Client = self._client._client  # acceso al httpx interno
                # Limpieza y actualización idempotente
                if "axet-user-id" in http_client.headers:
                    del http_client.headers["axet-user-id"]
                if "axet-asset-id" in http_client.headers:
                    del http_client.headers["axet-asset-id"]
                http_client.headers.update(self._build_default_headers())
                logger.info("🔁 Headers actualizados en el http_client existente")
            except Exception as e:
                # Si cambia la API interna, recreamos el cliente de forma segura
                logger.warning(f"No se pudo actualizar headers en caliente ({e}), recreando cliente…")
                self._client = None  # forzamos recreación perezosa

    @property
    def client(self) -> AzureOpenAI:
        """Crea o devuelve el cliente OpenAI."""
        if self._client is None:
            try:
                logger.info("Creating AzureOpenAI client:")
                logger.info(f"  Endpoint: {self.azure_endpoint}")
                logger.info(f"  Deployment: {self.deployment_name}")
                logger.info(f"  API Version: {self.api_version}")

                default_headers = self._build_default_headers()

                if "axet-user-id" in default_headers:
                    logger.info(f"  Header: axet-user-id = {default_headers['axet-user-id']}")
                if "axet-asset-id" in default_headers:
                    logger.info(f"  Header: axet-asset-id = {default_headers['axet-asset-id']}")

                http_client = httpx.Client(
                    timeout=60.0,
                    follow_redirects=True,
                    headers=default_headers
                )

                self._client = AzureOpenAI(
                    azure_endpoint=self.azure_endpoint,
                    api_key=self.bearer_token,
                    api_version=self.api_version,
                    http_client=http_client
                )

                logger.info("✅ Azure OpenAI client created")

            except Exception as e:
                logger.error(f"❌ Failed to create client: {str(e)}")
                raise ValueError(f"Client init failed: {str(e)}")

        return self._client

    def invoke(self, prompt: Union[str, List[Dict[str, Any]]], **kwargs: Any) -> str:
        """
        Invoca el modelo.

        Args:
            prompt: String con el prompt O lista de mensajes en formato OpenAI
            **kwargs:
                - temperature, max_tokens
                - axet_user_id (opcional): para override puntual
                - asset_id (opcional): para override puntual del header
        """
        try:
            # Overrides puntuales de headers (opcionales, sin hardcodear)
            axet_user_id_override = kwargs.pop("axet_user_id", None)
            asset_id_override = kwargs.pop("asset_id", None)
            if axet_user_id_override is not None or asset_id_override is not None:
                self.update_headers(
                    axet_user_id=axet_user_id_override,
                    axet_asset_id=asset_id_override
                )

            temperature = kwargs.get('temperature', self.temperature)
            max_tokens = kwargs.get('max_tokens', self.max_tokens)

            # Normalización de mensajes
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
                logger.info(f"Invoking (prompt string: {len(prompt)} chars, temp: {temperature}, max_tokens: {max_tokens})")
            elif isinstance(prompt, list):
                messages = prompt
                total_chars = sum(len(str(m.get('content', ''))) for m in messages)
                logger.info(f"Invoking (messages array: {len(messages)} msgs, {total_chars} chars, temp: {temperature}, max_tokens: {max_tokens})")
            else:
                raise ValueError(f"Prompt debe ser string o list, recibido: {type(prompt)}")

            clean_messages = []
            for msg in messages:
                if not isinstance(msg, dict):
                    logger.warning(f"Mensaje no es dict, convirtiendo: {type(msg)}")
                    continue

                if 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str):
                        clean_messages.append({"role": msg.get('role', 'user'), "content": content})
                    elif isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get('type') == 'text':
                                text_parts.append(part.get('text', ''))
                            elif isinstance(part, str):
                                text_parts.append(part)
                        if text_parts:
                            clean_messages.append({"role": msg.get('role', 'user'), "content": " ".join(text_parts)})
                    else:
                        clean_messages.append({"role": msg.get('role', 'user'), "content": str(content)})

            if not clean_messages:
                raise ValueError("No se pudieron construir mensajes válidos")

            logger.info(f"  Enviando {len(clean_messages)} mensajes limpios")

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=clean_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            logger.info(f"✅ Response: {len(content)} chars")
            return content

        except Exception as e:
            logger.error(f"❌ Invocation failed: {str(e)}")
            logger.error(f"   Prompt type: {type(prompt)}")
            if isinstance(prompt, list):
                logger.error(f"   Messages count: {len(prompt)}")
                if prompt:
                    logger.error(f"   First message: {prompt[0]}")
            raise

    def test_connection(self) -> bool:
        """Prueba la conexión."""
        try:
            logger.info("🔍 Testing connection...")

            # Test DNS
            import socket
            try:
                hostname = self.azure_endpoint.split('/')[2]
                logger.info(f"  DNS: {hostname}")
                ip = socket.gethostbyname(hostname)
                logger.info(f"  ✅ DNS OK: {hostname} → {ip}")
            except socket.gaierror as e:
                logger.error(f"  ❌ DNS FAILED: {e}")
                return False

            # Test invocación
            response = self.invoke("Say 'OK' if you can read this.")
            success = "OK" in response.upper()

            if success:
                logger.info("✅ Connection test PASSED")
            else:
                logger.warning(f"⚠️ Unexpected response: {response}")

            return success

        except Exception as e:
            logger.error(f"❌ Connection test failed: {str(e)}")
            return False
