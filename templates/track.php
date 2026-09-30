<?php
/** @var array $track @var array $positions @var array $links @var ?int $peak */
$points = array_map(fn ($p) => ['label' => fmt_date($p['period_end'], false), 'position' => (int) $p['position']], $positions);
$size = $positions ? (int) end($positions)['chart_size'] : 20;
?>
<article class="profile">
    <header class="profile__head">
        <span class="cover cover--large" aria-hidden="true">
            <?php if ($track['cover_url']): ?>
                <img src="<?= e($track['cover_url']) ?>" alt="" width="160" height="160">
            <?php else: ?>
                <span class="cover__initials"><?= e(initials($track['title'])) ?></span>
            <?php endif; ?>
        </span>
        <div>
            <p class="eyebrow"><?= e(t('track.eyebrow', ['country' => country_name($track['country_code'])])) ?></p>
            <h1 class="profile__title"><?= e($track['title']) ?></h1>
            <p class="profile__sub">
                <a href="<?= path('artiste/' . $track['artist_slug']) ?>"><?= e($track['artist_name']) ?></a>
                <?php if ($track['featuring']): ?> <span class="feat">feat. <?= e($track['featuring']) ?></span><?php endif; ?>
                <?php if (is_group_label($track['label_owner'])): ?>
                    <a class="badge" href="<?= path('methodologie') ?>#independance" title="<?= e(t('badge.title')) ?>"><?= e(\Cauri\Core\Config::get('app.group_label.name')) ?></a>
                <?php endif; ?>
            </p>
        </div>
    </header>

    <dl class="stats">
        <div><dt><?= e(t('track.peak')) ?></dt><dd><?= $peak ? '#' . $peak : '—' ?></dd></div>
        <div><dt><?= e(t('track.weeks')) ?></dt><dd><?= count($positions) ?></dd></div>
        <div><dt><?= e(t('track.release')) ?></dt><dd><?= $track['release_date'] ? e(fmt_date($track['release_date'])) : '—' ?></dd></div>
    </dl>

    <section class="panel">
        <h2 class="section-title"><?= e(t('track.curve', ['chart' => chart_name('prime')])) ?></h2>
        <?php if ($points): ?>
            <?= rank_chart_svg($points, $size, t('track.curve', ['chart' => chart_name('prime')])) ?>
            <details class="table-view">
                <summary><?= e(t('track.table')) ?></summary>
                <table>
                    <thead><tr><th scope="col"><?= e(t('track.week')) ?></th><th scope="col"><?= e(t('track.position')) ?></th></tr></thead>
                    <tbody>
                    <?php foreach (array_reverse($positions) as $p): ?>
                        <tr><td><a href="<?= chart_path($track['country_code'], 'prime', 'week', $p['period_key']) ?>"><?= e(period_label($p + ['period_type' => 'week'])) ?></a></td><td>#<?= (int) $p['position'] ?></td></tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </details>
        <?php else: ?>
            <p class="empty"><?= e(t('track.never_charted')) ?></p>
        <?php endif; ?>
    </section>

    <?php
    $clip = null;
    foreach ($links as $l) {
        if ($l['platform'] === 'youtube' && !$clip) {
            $clip = $l;
        }
    }
    ?>
    <?php if ($clip && \Cauri\Core\Config::get('app.tracking.youtube_embeds')): ?>
    <section class="panel">
        <h2 class="section-title"><?= e(t('track.clip')) ?></h2>
        <!-- Rien n'est chargé depuis YouTube avant le clic (ni lecteur, ni miniature) -->
        <div class="video" data-yt-id="<?= e($clip['external_id']) ?>" data-yt-title="<?= e($track['title']) ?>">
            <button class="video__play" type="button" data-yt-play>
                <span class="video__icon" aria-hidden="true">▶</span>
                <span><?= e(t('track.clip_play')) ?></span>
            </button>
            <p class="video__notice"><?= e(t('track.clip_notice')) ?> <a href="<?= e($clip['url']) ?>" rel="noopener nofollow" target="_blank"><?= e(t('track.clip_open')) ?></a></p>
        </div>
    </section>
    <?php endif; ?>

    <section class="panel">
        <h2 class="section-title"><?= e(t('track.listen')) ?></h2>
        <?php if (!empty($spotify)): ?>
        <p class="spotify-figure">
            <span class="source source--spotify"><span class="source__name">Spotify</span></span>
            <strong><?= e(fmt_number((int) $spotify['streams'])) ?></strong> <?= e(t('track.spotify_streams', ['start' => fmt_date($spotify['start'], false), 'end' => fmt_date($spotify['end'], false)])) ?>
        </p>
        <?php endif; ?>
        <ul class="platform-links">
            <li><a class="platform-links__spotify" href="<?= e(spotify_url($track['artist_spotify'] ?? null, $track['artist_name'], $track['title'])) ?>" rel="noopener nofollow" target="_blank">Spotify</a></li>
            <?php foreach ($links as $l): ?>
                <?php if ($l['platform'] === 'spotify') { continue; } ?>
                <li><a href="<?= e($l['url']) ?>" rel="noopener nofollow" target="_blank"><?= e(platform_name($l['platform'])) ?></a></li>
            <?php endforeach; ?>
        </ul>
        <?php if (empty($spotify)): ?>
        <p class="fineprint"><?= e(t('track.spotify_cta')) ?> <a href="<?= path('declarer') ?>"><?= e(t('track.spotify_cta_link')) ?></a></p>
        <?php endif; ?>
    </section>
</article>
