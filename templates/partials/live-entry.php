<?php
/**
 * Ligne d'un classement des plateformes (vue en direct ou vue d'une plateforme).
 * @var array $e ['rank', 'title', 'artist_name', 'seen' => [['source', 'country', 'position']], ...]
 * @var bool $showSourceCountry  afficher le pays du classement dans les pastilles (vue régionale)
 */
use Cauri\Services\Charts\LiveChart;

$showSourceCountry ??= false;
$compact ??= false; // encarts de l'accueil : sans pastilles
$isArtist = !empty($e['is_artist']); // Icon : une ligne par artiste
$cover = $isArtist ? ($e['artist_image'] ?: $e['cover_url']) : ($e['cover_url'] ?: $e['artist_image']);
?>
<li class="entry entry--live<?= $e['rank'] === 1 ? ' entry--top' : '' ?><?= $compact ? ' entry--compact' : '' ?>">
    <?php if ($e['rank'] === 1): ?>
    <span class="particles" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>
    <?php endif; ?>
    <span class="entry__rank"><?= (int) $e['rank'] ?></span>
    <span class="cover<?= $isArtist ? ' cover--round' : '' ?>" aria-hidden="true">
        <?php if ($cover): ?>
            <img src="<?= e($cover) ?>" alt="" width="56" height="56" loading="lazy">
        <?php else: ?>
            <span class="cover__initials"><?= e(initials($e['title'])) ?></span>
        <?php endif; ?>
    </span>
    <span class="entry__main">
        <?php if ($isArtist): ?>
        <a class="entry__title" href="<?= path('artiste/' . $e['artist_slug']) ?>"><?php if ($e['artist_country']): ?><?= flag($e['artist_country'], 12) ?> <?php endif; ?><?= e($e['artist_name']) ?></a>
        <span class="entry__artist"><?= e(t('chart.icon_line', ['n' => $e['titles'], 'title' => $e['top_title']])) ?></span>
        <?php else: ?>
        <a class="entry__title" href="<?= path('titre/' . $e['track_slug']) ?>"><?= e($e['title']) ?></a>
        <span class="entry__artist">
            <?php if ($e['artist_country']): ?><span class="entry__country" title="<?= e(country_name($e['artist_country'])) ?>"><?= flag($e['artist_country'], 12) ?></span><?php endif; ?>
            <a href="<?= path('artiste/' . $e['artist_slug']) ?>"><?= e($e['artist_name']) ?></a><?php if ($e['featuring']): ?> <span class="feat">feat. <?= e($e['featuring']) ?></span><?php endif; ?>
        </span>
        <?php endif; ?>
        <?php if (!$compact): ?>
        <ul class="sources" aria-label="<?= e(t('chart.sources_label')) ?>">
            <?php foreach (array_slice($e['seen'], 0, 5) as $s): ?>
            <li class="source source--<?= e($s['source'] === 'youtube_trending' || $s['source'] === 'youtube_discovery' ? 'youtube' : $s['source']) ?>" title="<?= e(LiveChart::SOURCES[$s['source']] . ' ' . country_name($s['country']) . ' : n° ' . $s['position']) ?>">
                <span class="source__name"><?= e(LiveChart::SOURCES[$s['source']]) ?><?= $showSourceCountry ? ' ' . e($s['country']) : '' ?></span>
                <span class="source__value">#<?= (int) $s['position'] ?></span>
            </li>
            <?php endforeach; ?>
            <?php $sp = $e['spotify_declared'] ?? null; // écoutes déclarées (Spotify for Artists), vérifiées ?>
            <li>
                <a class="source source--spotify source--link" href="<?= e(spotify_url($e['artist_spotify'] ?? null, $e['artist_name'], $isArtist ? null : $e['title'])) ?>" target="_blank" rel="noopener nofollow"
                   title="<?= e($sp ? t('chart.spotify_declared_long', ['n' => fmt_number((int) $sp['streams']), 'start' => fmt_date($sp['start'], false), 'end' => fmt_date($sp['end'], false)]) : t('chart.spotify_listen')) ?>">
                    <span class="source__name">Spotify</span>
                    <span class="source__value"><?= $sp ? e(t('chart.spotify_declared', ['n' => fmt_number((int) $sp['streams'])])) : '↗' ?></span>
                </a>
            </li>
        </ul>
        <?php endif; ?>
    </span>
</li>
