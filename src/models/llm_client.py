"""Module kết nối và quản lý tương tác với Google Gemini Flash.

Cung cấp lớp GeminiClient bọc (wrapper) Google GenAI SDK, hỗ trợ:
- Khởi tạo kết nối với API key từ biến môi trường
- Gọi Gemini Flash với system instruction và prompt
- Trả về Structured Output (JSON) hoặc text thuần
- Quản lý retry và xử lý lỗi API
"""

import json
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GeminiClient:
    """Client quản lý kết nối và gọi mô hình Gemini Flash.

    Attributes:
        model_name: Tên mô hình Gemini sử dụng.
        temperature: Nhiệt độ sinh (0.0 - 2.0). Thấp = ổn định, cao = sáng tạo.
        max_output_tokens: Giới hạn token đầu ra.
        client: Instance google.genai.Client.
    """

    def __init__(
        self,
        model_name: str = "gemini-3.8-flash",
        temperature: float = 0.1,
        max_output_tokens: int = 2048,
        api_key: str | None = None,
    ) -> None:
        """Khởi tạo GeminiClient.

        Args:
            model_name: Tên mô hình (mặc định gemini-3.8-flash).
            temperature: Nhiệt độ sinh.
            max_output_tokens: Số token tối đa cho phản hồi.
            api_key: API key. Nếu None, đọc từ biến môi trường GOOGLE_API_KEY.

        Raises:
            ValueError: Khi không tìm thấy API key.
        """
        # Load .env nếu có
        load_dotenv()

        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        # Lấy API key
        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Không tìm thấy GOOGLE_API_KEY. "
                "Vui lòng đặt biến môi trường hoặc tạo file .env."
            )

        # Khởi tạo client
        self.client = genai.Client(api_key=resolved_key)
        logger.info(
            "Đã khởi tạo GeminiClient: model=%s, temperature=%.2f",
            self.model_name,
            self.temperature,
        )

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_mime_type: str | None = None,
        response_schema: dict | None = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> str:
        """Gọi Gemini Flash và trả về text phản hồi.

        Args:
            prompt: Nội dung prompt chính (user message).
            system_instruction: System instruction cho model (vai trò, quy tắc).
            response_mime_type: MIME type cho structured output
                (ví dụ "application/json").
            response_schema: JSON schema cho structured output.
            max_retries: Số lần retry tối đa khi gặp lỗi API.
            retry_delay: Thời gian chờ giữa các lần retry (giây).

        Returns:
            Chuỗi text phản hồi từ Gemini.

        Raises:
            RuntimeError: Khi tất cả retry đều thất bại.
        """
        # Xây dựng config
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

        config = types.GenerateContentConfig(**config_kwargs)

        # Gọi API với retry
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    "Gọi Gemini (lần %d/%d): prompt length=%d",
                    attempt,
                    max_retries,
                    len(prompt),
                )

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )

                result_text = response.text
                if result_text is None:
                    # Kiểm tra block reason
                    if response.candidates and response.candidates[0].finish_reason:
                        reason = response.candidates[0].finish_reason
                        logger.warning("Phản hồi bị chặn: finish_reason=%s", reason)
                        raise RuntimeError(
                            f"Gemini từ chối phản hồi: {reason}"
                        )
                    raise RuntimeError("Gemini trả về phản hồi rỗng.")

                logger.info(
                    "Gemini phản hồi thành công: %d ký tự", len(result_text)
                )
                return result_text

            except Exception as e:
                last_error = e
                logger.warning(
                    "Lỗi gọi Gemini (lần %d/%d): %s",
                    attempt,
                    max_retries,
                    str(e),
                )
                if attempt < max_retries:
                    wait = retry_delay * attempt
                    logger.info("Chờ %.1f giây trước khi retry...", wait)
                    time.sleep(wait)

        raise RuntimeError(
            f"Không thể gọi Gemini sau {max_retries} lần thử. "
            f"Lỗi cuối: {last_error}"
        )

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: dict | None = None,
        max_retries: int = 3,
    ) -> dict | list:
        """Gọi Gemini và parse kết quả JSON.

        Sử dụng Structured Output của Gemini (response_mime_type=application/json)
        để đảm bảo output luôn là JSON hợp lệ.

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
            logger.debug("Raw response: %s", raw_text[:500])

            # Thử tìm JSON trong response (có thể có text wrapper)
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
    # Test nhanh kết nối
    print("=" * 60)
    print("TEST KET NOI GEMINI FLASH")
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
