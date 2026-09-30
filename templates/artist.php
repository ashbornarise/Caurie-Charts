<?php
/**
 * Fiche artiste : chiffres réels en avant (fans, vues YouTube, positions dans les classements des plateformes),
 * puis ses titres, puis son historique au classement officiel.
 * @var array $artist @var array $live @var ?int $iconRank @var array $tracks @var ?int $bestPeak @var int $totalWeeks @var array $iconHistory
 */
use Cauri\Services\Charts\LiveChart;

$points = array_map(fn ($p) => ['label' => fmt_date($p['period_end'], false), 'position' => (int) $p['position']], $iconHistory);
$best = $live['positions'][0] ?? null;
$confirmed = $artist['status'] === 'active';
$countryCode = $confirmed ? $artist['country_code'] : ($artist['base_country'] ?: null);
?>
<article class="profile profile--rich">
    <header class="artist-hero">
        <span class="artist-hero__photo" aria-hidden="true">
            <?php if ($artist['image_url']): ?>
                <img src="<?= e($artist['image_url']) ?>" alt="" width="220" height="220">
            <?php else: ?>
                <span class="cover__initials"><?= e(initials($artist['name'])) ?></span>
            <?php endif; ?>
        </span>
        <div class="artist-hero__text">
            <p class="eyebrow">
                <?php if ($countryCode && strlen($countryCode) === 2 && in_array($countryCode, ['TG', 'BJ', 'GH', 'CI', 'SN'], true)): ?><?= flag($countryCode, 14) ?> <?= e(t('artist.eyebrow', ['country' => country_name($countryCode)])) ?>
                <?php else: ?><?= e(t('artist.eyebrow_unknown')) ?><?php endif; ?>
            </p>
            <h1 class="profile__title"><?= e($artist['name']) ?></h1>
            <?php if ($iconRank): ?>
                <p class="artist-hero__rank"><?= e(t('artist.icon_rank', ['n' => $iconRank])) ?></p>
            <?php endif; ?>
            <p class="artist-hero__links">
                <a class="button button--small platform-links__spotify" href="<?= e(spotify_url($artist['spotify_id'] ?? null, $artist['name'])) ?>" target="_blank" rel="noopener nofollow">Spotify</a>
                <?php if (!empty($artist['deezer_id'])): ?><a class="button button--small button--ghost" href="https://www.deezer.com/artist/<?= (int) $artist['deezer_id'] ?>" target="_blank" rel="noopener nofollow">Deezer</a><?php endif; ?>
                <?php if (!empty($artist['youtube_channel_id'])): ?><a class="button button--small button--ghost" href="https://www.youtube.com/channel/<?= e(rawurlencode($artist['youtube_channel_id'])) ?>" target="_blank" rel="noopener nofollow">YouTube</a><?php endif; ?>
            </p>
            <?php if (!$confirmed): ?><p class="fineprint"><?= e(t('artist.pending_note')) ?></p><?php endif; ?>
            <?php if (is_group_label($artist['label_owner'])): ?>
                <a class="badge" href="<?= path('methodologie') ?>#independance" title="<?= e(t('badge.title')) ?>"><?= e(\Cauri\Core\Config::get('app.group_label.name')) ?></a>
            <?php endif; ?>
            <?php if ($artist['bio']): ?><p><?= nl2br(e($artist['bio'])) ?></p><?php endif; ?>
        </div>
    </header>

    <dl class="stat-tiles">
        <div class="stat-tile stat-tile--accent">
            <dt><?= e(t('artist.stat_best')) ?></dt>
            <dd><?= $best ? '#' . (int) $best['best'] : '—' ?></dd>
            <?php if ($best): ?><small><?= e(LiveChart::SOURCES[$best['source']] . ' · ' . country_name($best['country'])) ?></small><?php endif; ?>
        </div>
        <div class="stat-tile">
            <dt><?= e(t('artist.stat_charts')) ?></dt>
            <dd><?= (int) $live['charts_count'] ?></dd>
            <small><?= e(t('artist.stat_charts_note')) ?></small>
        </div>
        <div class="stat-tile">
            <dt><?= e(t('artist.stat_views')) ?></dt>
            <dd><?= $live['views_total'] !== null ? e(fmt_number($live['views_total'])) : '—' ?></dd>
            <small><?= $live['views_week'] ? e(t('artist.stat_views_week', ['n' => fmt_number($live['views_week'])])) : e(t('artist.stat_views_note')) ?></small>
        </div>
        <div class="stat-tile">
            <dt><?= e(t('artist.stat_fans')) ?></dt>
            <dd><?= $artist['fans'] ? e(fmt_number((int) $artist['fans'])) : '—' ?></dd>
            <small>Deezer</small>
        </div>
    </dl>

    <?php if ($live['positions']): ?>
    <section class="panel">
        <h2 class="section-title"><?= e(t('artist.this_week')) ?></h2>
        <div class="table-scroll">
        <table class="data-table data-table--positions">
            <thead><tr><th><?= e(t('artist.col_position')) ?></th><th><?= e(t('artist.col_chart')) ?></th><th><?= e(t('artist.col_title')) ?></th></tr></thead>
            <tbody>
            <?php foreach (array_slice($live['positions'], 0, 12) as $p): ?>
                <tr>
                    <td class="num"><strong>#<?= (int) $p['best'] ?></strong></td>
                    <td><span class="source source--<?= e(str_starts_with($p['source'], 'youtube') ? 'youtube' : $p['source']) ?>"><span class="source__name"><?= e(LiveChart::SOURCES[$p['source']]) ?></span></span> <?= flag($p['country'], 12) ?> <?= e(country_name($p['country'])) ?></td>
                    <td><a href="<?= path('titre/' . $p['track_slug']) ?>"><?= e($p['title']) ?></a></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
        </div>
    </section>
    <?php endif; ?>

    <section class="panel">
        <h2 class="section-title"><?= e(t('artist.tracks')) ?></h2>
        <ul class="artist-tracks">
            <?php foreach ($live['tracks'] as $t): ?>
            <li>
                <span class="cover" aria-hidden="true">
                    <?php if ($t['cover_url']): ?><img src="<?= e($t['cover_url']) ?>" alt="" width="48" height="48" loading="lazy">
                    <?php else: ?><span class="cover__initials"><?= e(initials($t['title'])) ?></span><?php endif; ?>
                </span>
                <span class="artist-tracks__main">
                    <a href="<?= path('titre/' . $t['slug']) ?>" class="track-table__title"><?= e($t['title']) ?><?php if ($t['featuring']): ?> <span class="feat">feat. <?= e($t['featuring']) ?></span><?php endif; ?></a>
                    <small class="muted">
                        <?php if ($t['best_ever']): ?><?= e(t('artist.track_best', ['n' => (int) $t['best_ever'], 'chart' => LiveChart::SOURCES[$t['best_source']] ?? $t['best_source'], 'country' => $t['best_country']])) ?><?php endif; ?>
                        <?php if ($t['release_date']): ?> · <?= e(t('artist.track_released', ['date' => fmt_date($t['release_date'])])) ?><?php endif; ?>
                    </small>
                </span>
                <span class="artist-tracks__views"><?= $t['views'] !== null ? '<strong>' . e(fmt_number($t['views'])) . '</strong> ' . e(t('chart.views')) : '' ?></span>
            </li>
            <?php endforeach; ?>
        </ul>
        <?php if ($live['measured_on']): ?><p class="fineprint"><?= e(t('artist.views_source', ['date' => fmt_date($live['measured_on'])])) ?></p><?php endif; ?>
    </section>

    <section class="panel">
        <h2 class="section-title"><?= e(t('artist.official')) ?></h2>
        <dl class="stats">
            <div><dt><?= e(t('artist.best')) ?></dt><dd><?= $bestPeak ? '#' . $bestPeak : '—' ?></dd></div>
            <div><dt><?= e(t('artist.weeks')) ?></dt><dd><?= (int) $totalWeeks ?></dd></div>
            <div>
                <dt><?= e(t('artist.top_country')) ?></dt>
                <dd><?= $artist['top_country_code'] ? e(country_name($artist['top_country_code'])) : '—' ?></dd>
            </div>
        </dl>
        <p class="fineprint"><?= e($bestPeak ? t('artist.country_rule', ['country' => country_name($artist['country_code'])]) : t('artist.official_soon')) ?></p>
        <?php if (count($points) > 1): ?>
            <?= rank_chart_svg($points, 10, t('artist.icon_curve', ['chart' => chart_name('icon')])) ?>
        <?php endif; ?>
    </section>
</article>
