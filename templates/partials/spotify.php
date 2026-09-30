<?php
/**
 * Playlist Spotify de Cauri Charts : aperçu et bouton ; le lecteur Spotify (qui dépose ses propres cookies)
 * ne se charge qu'au clic, ou d'office si le visiteur a accepté les contenus intégrés.
 * @var string $playlist identifiant de la playlist
 */
?>
<section class="spotify-block" aria-labelledby="spotify-title">
    <div class="partners__head">
        <div>
            <h2 id="spotify-title"><?= e(t('spotify.title')) ?></h2>
            <p class="partners__lead"><?= e(t('spotify.lead')) ?></p>
        </div>
    </div>
    <div class="spotify" data-spotify-playlist="<?= e($playlist) ?>" data-spotify-title="<?= e(t('spotify.title')) ?>">
        <button class="spotify__play" type="button" data-spotify-play>
            <span class="spotify__icon" aria-hidden="true">▶</span>
            <span><?= e(t('spotify.play')) ?></span>
        </button>
        <p class="spotify__notice"><?= e(t('spotify.notice')) ?>
            <a href="https://open.spotify.com/playlist/<?= e(rawurlencode($playlist)) ?>" target="_blank" rel="noopener nofollow"><?= e(t('spotify.open')) ?></a>
        </p>
    </div>
</section>
