import pytest

from baixai_helper.platforms import detect, is_compatible_link


@pytest.mark.parametrize("url,platform,kind,first_engine", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube", "video", "ytdlp"),
    ("https://youtu.be/dQw4w9WgXcQ", "youtube", "video", "ytdlp"),
    ("https://www.youtube.com/shorts/abc", "youtube", "video", "ytdlp"),
    ("https://www.youtube.com/playlist?list=PL123", "youtube", "playlist", "ytdlp"),
    ("https://www.youtube.com/@canal", "youtube", "channel", "ytdlp"),
    ("https://www.instagram.com/reel/ABC/", "instagram", "video", "ytdlp"),
    ("https://www.instagram.com/p/ABC/", "instagram", "post", "gallerydl"),
    ("https://www.tiktok.com/@u/video/123", "tiktok", "video", "ytdlp"),
    ("https://vm.tiktok.com/ZM123/", "tiktok", "video", "ytdlp"),
    ("https://www.tiktok.com/@u/photo/123", "tiktok", "photo", "gallerydl"),
    ("https://x.com/user/status/123", "twitter", "post", "ytdlp"),
    ("https://twitter.com/user/status/123", "twitter", "post", "ytdlp"),
    ("https://soundcloud.com/artista/faixa", "soundcloud", "track", "ytdlp"),
    ("https://soundcloud.com/artista/sets/album", "soundcloud", "playlist", "ytdlp"),
])
def test_detecta_plataforma_tipo_e_motor(url, platform, kind, first_engine):
    d = detect(url)
    assert (d.platform, d.kind, d.engines[0]) == (platform, kind, first_engine) and d.supported


@pytest.mark.parametrize("url", ["https://example.com/a.jpg", "https://evilyoutube.com/watch?v=1", "https://youtube.com.evil.com/watch?v=1", "https://notx.com/u/status/1"])
def test_hosts_desconhecidos_ou_imitacoes_nao_sao_plataforma(url):
    assert detect(url) is None


@pytest.mark.parametrize("url", ["https://www.instagram.com/someuser/", "https://www.instagram.com/stories/u/1/", "https://x.com/user", "https://soundcloud.com/artista", "https://www.tiktok.com/@u"])
def test_links_de_perfil_nao_suportados_com_orientacao(url):
    d = detect(url)
    assert d is not None and not d.supported and d.note and not is_compatible_link(url)
