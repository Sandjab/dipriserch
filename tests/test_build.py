import shutil


def test_build_produit_html(run_dir, fixtures_dir):
    import build

    shutil.copy(fixtures_dir / "manifest.json",       run_dir / "manifest.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    widgets_dir = run_dir / "widgets"
    widgets_dir.mkdir()
    shutil.copy(fixtures_dir / "widget_1.html", widgets_dir / "widget_1.html")

    css_path = fixtures_dir.parent.parent / "assets" / "style.css"
    build.build(run_dir, css_path=css_path)

    html = (run_dir / "output.html").read_text()
    assert "<html" in html
    assert "Introduction" in html
    assert "Gradient Descent" in html
    assert "Descente de gradient interactive" in html
    assert 'id="widget-gradient-descent"' in html


def test_build_echoue_si_widget_manquant(run_dir, fixtures_dir):
    import build
    import pytest

    shutil.copy(fixtures_dir / "manifest.json",       run_dir / "manifest.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    (run_dir / "widgets").mkdir()
    # widget_1.html intentionnellement absent

    with pytest.raises(FileNotFoundError, match="widget_1.html"):
        build.build(run_dir)
