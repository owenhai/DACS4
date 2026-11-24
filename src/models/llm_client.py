"""Module kết nối và quản lý tương tác với Google Gemini.

Cung cấp lớp GeminiClient bọc (wrapper) Google GenAI SDK, hỗ trợ:
- Khởi tạo kết nối với API key từ biến môi trường
- Gọi Gemini với system instruction và prompt
- Trả về Structured Output (JSON) hoặc text thuần
- Quản lý retry, fallback model và xử lý lỗi API
- Cache phản hồi trên đĩa để không gọi lại API cho prompt trùng lặp
"""

import hashlib
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Thư mục cache mặc định: <project_root>/cache/llm_responses
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE_DIR = _PROJECT_ROOT / "cache" / "llm_responses"


class GeminiClient:
    """Client quản lý kết nối và gọi mô hình Gemini.

    Attributes:
        model_name: Tên mô hình Gemini chính.
        fallback_model: Mô hình dự phòng khi mô hình chính quá tải.
        temperature: Nhiệt độ sinh (0.0 - 2.0). Thấp = ổn định, cao = sáng tạo.
        max_output_tokens: Giới hạn token đầu ra.
        use_cache: Bật/tắt cache phản hồi trên đĩa.
        cache_dir: Thư mục lưu cache.
        client: Instance google.genai.Client.
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.1,
        max_output_tokens: int = 768,
        api_key: str | None = None,
        fallback_model: str | None = None,
        use_cache: bool | None = None,
        cache_dir: str | Path | None = None,
        request_timeout: float | None = None,
        thinking_level: str | None = None,
    ) -> None:
        """Khởi tạo GeminiClient.

        Mặc định dùng ``gemini-3.5-flash-lite`` (đo ngày 19/11/2026: trung vị
        ~1.6s/câu, 3/3 SQL đúng) và dự phòng ``gemini-3.5-flash``.
        ``gemini-3.8-flash`` khi đó bị quá tải (503, 47-90s/câu).

        Args:
            model_name: Tên mô hình. Nếu None, đọc GEMINI_MODEL hoặc dùng
                ``gemini-3.5-flash-lite``.
            temperature: Nhiệt độ sinh.
            max_output_tokens: Số token tối đa cho phản hồi.
            api_key: API key. Nếu None, đọc GEMINI_API_KEY hoặc GOOGLE_API_KEY.
            fallback_model: Model dự phòng, có thể là danh sách phân tách bằng
                dấu phẩy. Nếu None, đọc GEMINI_FALLBACK_MODEL hoặc dùng
                ``gemini-3.5-flash-lite,gemini-3.5-flash``. Đặt
                GEMINI_FALLBACK_MODEL=none để tắt fallback.
            use_cache: Bật cache. Nếu None, đọc LLM_CACHE (mặc định bật;
                đặt LLM_CACHE=0 để tắt).
            cache_dir: Thư mục cache (mặc định cache/llm_responses).
            request_timeout: Thời gian tối đa (giây) cho mỗi request. Nếu None,
                đọc GEMINI_TIMEOUT hoặc dùng 20s (tối thiểu 10s). Quá thời gian -> chuyển
                sang fallback model ngay.
            thinking_level: Mức "thinking" (ví dụ "low"). Nếu None, đọc
                GEMINI_THINKING_LEVEL; không đặt = dùng mặc định của model.

        Raises:
            ValueError: Khi không tìm thấy API key.
        """
        load_dotenv()

        self.model_name = model_name or os.environ.get(
            "GEMINI_MODEL", "gemini-3.5-flash-lite"
        )
        fallback = fallback_model or os.environ.get(
            "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite,gemini-3.5-flash"
        )
        # Chuỗi fallback (phân tách bằng dấu phẩy), bỏ trùng và bỏ model chính
        self.fallback_models: list[str] = []
        for name in fallback.split(","):
            name = name.strip()
            if name and name.lower() != "none" and name != self.model_name \
                    and name not in self.fallback_models:
                self.fallback_models.append(name)
        self.fallback_model = self.fallback_models[0] if self.fallback_models else None
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        # API Gemini từ chối deadline < 10s (400 INVALID_ARGUMENT)
        self.request_timeout = max(10.0, float(
            request_timeout or os.environ.get("GEMINI_TIMEOUT", "20")
        ))
        self.thinking_level = thinking_level or os.environ.get("GEMINI_THINKING_LEVEL") or None

        if use_cache is None:
            use_cache = os.environ.get("LLM_CACHE", "1").strip() not in (
                "0", "false", "no", "off",
            )
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR

        resolved_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Không tìm thấy GEMINI_API_KEY. "
                "Vui lòng đặt biến môi trường hoặc tạo file .env."
            )

        # Timeout ở tầng HTTP (đơn vị ms) để một request chậm không treo pipeline
        self.client = genai.Client(
            api_key=resolved_key,
            http_options=types.HttpOptions(timeout=int(self.request_timeout * 1000)),
        )
        logger.info(
            "Đã khởi tạo GeminiClient: model=%s, fallback=%s, timeout=%.0fs, "
            "thinking=%s, cache=%s",
            self.model_name,
            self.fallback_model,
            self.request_timeout,
            self.thinking_level or "default",
            self.use_cache,
        )

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_key(
        self,
        prompt: str,
        system_instruction: str | None,
        response_mime_type: str | None,
        response_schema: dict | None,
    ) -> str:
        """Tạo khóa cache xác định từ prompt và cấu hình sinh."""
        source = json.dumps(
            {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
                "prompt": prompt,
                "system_instruction": system_instruction,
                "response_mime_type": response_mime_type,
                "response_schema": response_schema,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _cache_read(self, key: str) -> str | None:
        """Đọc phản hồi từ cache, trả về None nếu không có."""
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return data["response"]
        except Exception as e:  # File hỏng -> bỏ qua cache
            logger.warning("Không đọc được cache %s: %s", cache_file.name, e)
            return None

    def _cache_write(self, key: str, response: str) -> None:
        """Ghi phản hồi vào cache (lỗi ghi không làm hỏng luồng chính)."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.cache_dir / f"{key}.json"
            cache_file.write_text(
                json.dumps({"response": response}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Không ghi được cache: %s", e)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_mime_type: str | None = None,
        response_schema: dict | None = None,
        max_retries: int = 1,
        retry_delay: float = 2.0,
    ) -> str:
        """Gọi Gemini và trả về text phản hồi (có cache).

        Nếu prompt + cấu hình đã từng được gọi thành công, trả về kết quả từ
        cache mà không gọi API.

        Args:
            prompt: Nội dung prompt chính (user message).
            system_instruction: System instruction cho model.
            response_mime_type: MIME type cho structured output.
            response_schema: JSON schema cho structured output.
            max_retries: Số lần thử tối đa cho mỗi model khi gặp lỗi tạm thời.
            retry_delay: Thời gian chờ cơ sở giữa các lần retry (giây).

        Returns:
            Chuỗi text phản hồi từ Gemini.

        Raises:
            RuntimeError: Khi tất cả retry/fallback đều thất bại.
        """
        cache_key = None
        if self.use_cache:
            cache_key = self._cache_key(
                prompt, system_instruction, response_mime_type, response_schema
            )
            cached = self._cache_read(cache_key)
            if cached is not None:
                logger.info("Cache hit (key=%s...)", cache_key[:12])
                return cached

        result_text = self._call_api(
            prompt=prompt,
            system_instruction=system_instruction,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        if self.use_cache and cache_key:
            self._cache_write(cache_key, result_text)
        return result_text

    def _call_api(
        self,
        prompt: str,
        system_instruction: str | None,
        response_mime_type: str | None,
        response_schema: dict | None,
        max_retries: int,
        retry_delay: float,
    ) -> str:
        """Gọi API thực tế với retry + fallback model."""
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type
        if response_schema:
            config_kwargs["response_schema"] = response_schema
        if self.thinking_level:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=self.thinking_level
            )
        config = types.GenerateContentConfig(**config_kwargs)

        max_retries = max(1, max_retries)
        last_error: Exception | None = None
        models = [self.model_name, *self.fallback_models]

        for model_index, model_name in enumerate(models):
            for attempt in range(1, max_retries + 1):
                try:
                    start = time.perf_counter()
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    elapsed = time.perf_counter() - start

                    result_text = response.text
                    if result_text is None:
                        if response.candidates and response.candidates[0].finish_reason:
                            reason = response.candidates[0].finish_reason
                            raise RuntimeError(f"Gemini từ chối phản hồi: {reason}")
                        raise RuntimeError("Gemini trả về phản hồi rỗng.")

                    logger.info(
                        "Gemini (%s) phản hồi %d ký tự trong %.2fs",
                        model_name,
                        len(result_text),
                        elapsed,
                    )
                    return result_text

                except Exception as e:
                    last_error = e
                    if not self._is_transient_error(e):
                        # Lỗi model không tồn tại -> thử fallback thay vì dừng
                        if self._is_model_not_found(e) and model_index < len(models) - 1:
                            logger.warning(
                                "Model %s không khả dụng (%s); chuyển sang %s",
                                model_name, e, models[model_index + 1],
                            )
                            break
                        raise RuntimeError(
                            f"Gemini trả về lỗi không thể retry: {e}"
                        ) from e

                    logger.warning(
                        "Lỗi tạm thời Gemini (model=%s, lần %d/%d): %s",
                        model_name, attempt, max_retries, e,
                    )
                    # Timeout: thử lại cùng model chỉ tốn thêm thời gian -> sang fallback
                    if self._is_timeout(e):
                        break
                    if attempt < max_retries:
                        wait = min(retry_delay * (2 ** (attempt - 1)), 16.0)
                        wait += random.uniform(0, 0.5)
                        time.sleep(wait)

            if model_index < len(models) - 1:
                logger.warning(
                    "Model %s thất bại; chuyển sang fallback model %s",
                    model_name, models[model_index + 1],
                )

        raise RuntimeError(
            f"Không thể gọi Gemini sau {len(models)} model và "
            f"{max_retries} lần thử/model. Lỗi cuối: {last_error}"
        )

    @staticmethod
    def _is_timeout(error: Exception) -> bool:
        """Request vượt quá ``request_timeout``."""
        message = f"{type(error).__name__} {error}".lower()
        return (
            "timeout" in message
            or "timed out" in message
            or "deadline exceeded" in message
            or "deadline_exceeded" in message
            or "504" in message
        )

    @staticmethod
    def _is_transient_error(error: Exception) -> bool:
        """Xác định lỗi có khả năng tự hết và nên được retry."""
        message = f"{type(error).__name__} {error}".lower()
        transient_markers = (
            "503",
            "service unavailable",
            "unavailable",
            "429",
            "resource exhausted",
            "rate limit",
            "deadline exceeded",
            "deadline_exceeded",
            "504",
            "timed out",
            "timeout",
            "temporarily unavailable",
        )
        return any(marker in message for marker in transient_markers)

    @staticmethod
    def _is_model_not_found(error: Exception) -> bool:
        """Lỗi do model không tồn tại / không được hỗ trợ."""
        message = str(error).lower()
        return "404" in message or "not found" in message or "not supported" in message

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: dict | None = None,
        max_retries: int = 3,
    ) -> dict | list:
        """Gọi Gemini và parse kết quả JSON.

        Args:
            prompt: Nội dung prompt.
            system_instruction: System instruction.
            response_schema: JSON schema mong muốn.
            max_retries: Số lần retry.

        Returns:
            Dict hoặc list đã parse từ JSON.

        Raises:
            RuntimeError: Khi không parse được JSON.
        """
        raw_text = self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
            max_retries=max_retries,
        )

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error("Không parse được JSON từ Gemini: %s", str(e))
            start_idx = raw_text.find("{")
            if start_idx == -1:
                start_idx = raw_text.find("[")
            if start_idx != -1:
                try:
                    return json.loads(raw_text[start_idx:])
                except json.JSONDecodeError:
                    pass
            raise RuntimeError(
                f"Không thể parse JSON từ phản hồi Gemini: {raw_text[:200]}"
            ) from e


if __name__ == "__main__":
    print("=" * 60)
    print("TEST KET NOI GEMINI")
    print("=" * 60)

    try:
        client = GeminiClient()
        response = client.generate(
            prompt="Reply briefly: 2 + 2 = ?",
            system_instruction="You are a math assistant. Reply briefly.",
        )
        print(f"\nResult: {response}")
        print("\nConnection successful!")
    except ValueError as e:
        print(f"\nConfig error: {e}")
    except Exception as e:
        print(f"\nError: {e}")
