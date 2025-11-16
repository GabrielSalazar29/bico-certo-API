import uuid
from PIL import Image
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException
from pathlib import Path
import io


class ImageUtils:
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB em bytes
    BASE_UPLOAD_DIR = Path("uploads")

    @staticmethod
    def validate_image(file: UploadFile) -> Tuple[bool, str]:
        """Valida se o arquivo é uma imagem válida"""

        if not file.filename:
            return False, "Nome do arquivo inválido"

        extension = file.filename.rsplit('.', 1)[-1].lower()
        if extension not in ImageUtils.ALLOWED_EXTENSIONS:
            return False, f"Extensão não permitida. Use: {', '.join(ImageUtils.ALLOWED_EXTENSIONS)}"

        return True, "OK"

    @staticmethod
    def generate_filename(user_id: str, extension: str) -> str:
        """Gera nome único para o arquivo"""
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(uuid.uuid1().time)
        return f"profile_{user_id}_{timestamp}_{unique_id}.{extension}"

    @staticmethod
    async def save_profile_picture(
            file: UploadFile,
            user_id: str,
            max_size: Tuple[int, int] = (800, 800),
            quality: int = 85
    ) -> str:
        """
        Salva imagem de perfil com otimização

        Returns:
            str: Caminho relativo da imagem salva
        """
        is_valid, message = ImageUtils.validate_image(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        upload_dir = ImageUtils.BASE_UPLOAD_DIR / "profile_pictures"
        upload_dir.mkdir(parents=True, exist_ok=True)

        extension = file.filename.rsplit('.', 1)[-1].lower()

        if extension in ['jpg', 'jpeg']:
            extension = 'jpg'

        filename = ImageUtils.generate_filename(user_id, extension)
        file_path = upload_dir / filename

        try:
            contents = await file.read()

            if len(contents) > ImageUtils.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Arquivo muito grande. Máximo: {ImageUtils.MAX_FILE_SIZE / 1024 / 1024}MB"
                )

            try:
                image = Image.open(io.BytesIO(contents))
                image.verify()
                image = Image.open(io.BytesIO(contents))

            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Arquivo não é uma imagem válida: {str(e)}"
                )

            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            final_path = upload_dir / filename.rsplit('.', 1)[0]
            final_path = Path(str(final_path) + '.jpg')

            image.save(
                final_path,
                format='JPEG',
                quality=quality,
                optimize=True
            )

            relative_filename = final_path.name
            return f"profile_pictures/{relative_filename}"

        except HTTPException:
            raise
        except Exception as e:
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar imagem: {str(e)}"
            )

    @staticmethod
    def delete_old_profile_pictures(user_id: str, keep_current: Optional[str] = None):
        """Deleta fotos antigas do usuário"""

        upload_dir = ImageUtils.BASE_UPLOAD_DIR / "profile_pictures"
        if not upload_dir.exists():
            return

        pattern = f"profile_{user_id}_*"
        for file_path in upload_dir.glob(pattern):
            if keep_current and file_path.name == Path(keep_current).name:
                continue

            try:
                file_path.unlink()
            except Exception as e:
                pass

    @staticmethod
    def get_file_path(relative_path: str) -> Path:
        """Retorna o caminho absoluto do arquivo"""
        return ImageUtils.BASE_UPLOAD_DIR / relative_path