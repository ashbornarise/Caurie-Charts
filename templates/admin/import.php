<?php
/** @var array $coverage @var array $pending @var array $autoClips @var array $noClip @var array $countries @var array $sources @var string $today @var array $user */
use Cauri\Core\Csrf;

$countryOptions = function (?int $selected) use ($countries): string {
    $html = '<option value="">' . e(t('form.choose')) . '</option>';
    foreach ($countries as $c) {
        $html .= '<option value="' . (int) $c['id'] . '"' . ((int) $c['id'] === (int) $selected ? ' selected' : '') . '>' . e($c['code'] . ' · ' . country_name($c['code'])) . '</option>';
    }
    return $html;
};
?>
<h1><?= e(t('admin.nav_import')) ?></h1>
<p class="muted"><?= e(t('admin.import_intro')) ?></p>

<?php if ($user['role'] === 'admin'): ?>
<form method="post" action="<?= path('admin/import/lancer') ?>" class="toolbar box box--accent">
    <?= Csrf::field() ?>
    <button class="button" type="submit"><?= e(t('admin.import_run')) ?></button>
    <label class="checks"><?= e(t('admin.import_youtube')) ?> <input type="number" name="youtube" value="0" min="0" max="90" class="num"></label>
    <span class="fineprint"><?= e(t('admin.import_youtube_hint')) ?></span>
</form>
<?php endif; ?>

<h2><?= e(t('admin.import_coverage')) ?></h2>
<?php if (!$coverage): ?><p class="muted"><?= e(t('admin.none')) ?></p><?php else: ?>
<table class="data-table">
    <thead><tr><th><?= e(t('admin.platform')) ?></th><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.import_last')) ?></th><th class="num"><?= e(t('admin.import_days')) ?></th><th class="num"><?= e(t('admin.import_rows')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($coverage as $c): ?>
        <tr><td><?= e(platform_name($c['source'])) ?></td><td><?= e($c['code']) ?></td><td><?= e(fmt_date($c['last_day'])) ?></td><td class="num"><?= (int) $c['days'] ?></td><td class="num"><?= (int) $c['rows_count'] ?></td></tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php endif; ?>

<h2 id="artistes"><?= e(t('admin.import_pending', ['n' => count($pending)])) ?></h2>
<p class="muted"><?= e(t('admin.import_pending_intro')) ?></p>
<?php if ($pending): ?>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.artist')) ?></th><th><?= e(t('admin.import_seen_in')) ?></th><th class="num"><?= e(t('admin.import_best')) ?></th><th><?= e(t('admin.decision')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($pending as $a): ?>
        <tr>
            <td>
                <div class="candidate">
                    <?php if ($a['image_url']): ?><img class="candidate__photo" src="<?= e($a['image_url']) ?>" alt="" width="52" height="52" loading="lazy"><?php endif; ?>
                    <div>
                        <strong><a href="<?= path('artiste/' . $a['slug']) ?>" target="_blank" rel="noopener"><?= e($a['name']) ?></a></strong><br>
                        <small class="muted"><?= e((string) $a['a_track']) ?></small>
                        <p class="candidate__fans">
                            <?php if ($a['fans']): ?><span><strong><?= e(fmt_number((int) $a['fans'])) ?></strong> fans Deezer</span><?php endif; ?>
                            <?php if ($a['youtube_subscribers']): ?><span><strong><?= e(fmt_number((int) $a['youtube_subscribers'])) ?></strong> abonnés YouTube</span><?php endif; ?>
                        </p>
                        <?php if ($a['discovered_via']): ?><small class="muted"><?= e($a['discovered_via']) ?></small><?php endif; ?>
                    </div>
                </div>
                <?php if ($a['base_country']): ?>
                <p class="suggestion">
                    <strong><?= e(t('admin.import_suggestion', ['country' => $a['base_country'], 'pct' => (int) round($a['origin_confidence'] * 100)])) ?></strong>
                    <small><?= e(mb_substr((string) $a['origin_note'], 0, 260)) ?></small>
                </p>
                <?php endif; ?>
            </td>
            <td><small><?= e((string) $a['seen_in']) ?></small><br><small class="muted"><?= e(t('admin.import_observations', ['n' => $a['obs']])) ?></small></td>
            <td class="num"><?= $a['best_position'] ? '#' . (int) $a['best_position'] : '—' ?></td>
            <td>
                <form method="post" action="<?= path('admin/import/artiste/' . $a['id']) ?>" class="toolbar">
                    <?= Csrf::field() ?>
                    <label class="visually-hidden" for="c-<?= (int) $a['id'] ?>"><?= e(t('admin.submission_country')) ?></label>
                    <select id="c-<?= (int) $a['id'] ?>" name="country_id"><?= $countryOptions((int) ($a['suggested_country_id'] ?: $a['guessed_country_id'])) ?></select>
                    <button class="button button--small" name="action" value="confirm" type="submit"><?= e(t('admin.import_confirm_country')) ?></button>
                    <button class="button button--small button--ghost" name="action" value="out" type="submit"><?= e(t('admin.import_out_of_scope')) ?></button>
                </form>
            </td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php endif; ?>

<h2 id="clips"><?= e(t('admin.import_auto_clips', ['n' => count($autoClips)])) ?></h2>
<?php if (!$autoClips): ?><p class="muted"><?= e(t('admin.import_auto_clips_empty')) ?></p><?php else: ?>
<table class="data-table">
    <thead><tr><th><?= e(t('admin.track')) ?></th><th><?= e(t('track.clip')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($autoClips as $c): ?>
        <tr>
            <td><?= e($c['title']) ?> <span class="muted">· <?= e($c['artist']) ?></span></td>
            <td><a href="<?= e((string) $c['url']) ?>" target="_blank" rel="noopener"><?= e($c['external_id']) ?></a></td>
            <td><form method="post" action="<?= path('admin/import/clip/' . $c['id']) ?>" class="toolbar"><?= Csrf::field() ?>
                <button class="button button--small" name="action" value="confirm" type="submit"><?= e(t('admin.validate')) ?></button>
                <button class="button button--small button--danger" name="action" value="remove" type="submit"><?= e(t('admin.delete')) ?></button></form></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php endif; ?>

<h2 id="sans-clip"><?= e(t('admin.import_no_clip', ['n' => count($noClip)])) ?></h2>
<p class="muted"><?= e(t('admin.import_no_clip_intro')) ?></p>
<?php if ($noClip): ?>
<div class="table-scroll">
<table class="data-table">
    <tbody>
    <?php foreach ($noClip as $tr): ?>
        <tr>
            <td><?= e($tr['title']) ?> <span class="muted">· <?= e($tr['artist']) ?> (<?= e($tr['code']) ?>)</span></td>
            <td><form method="post" action="<?= path('admin/import/clip-manuel/' . $tr['id']) ?>" class="toolbar"><?= Csrf::field() ?>
                <label class="visually-hidden" for="v-<?= (int) $tr['id'] ?>"><?= e(t('admin.import_video')) ?></label>
                <input id="v-<?= (int) $tr['id'] ?>" name="video" placeholder="https://www.youtube.com/watch?v=…" required>
                <button class="button button--small" type="submit"><?= e(t('admin.save')) ?></button></form></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php endif; ?>

<h2 id="csv"><?= e(t('admin.import_csv')) ?></h2>
<p class="muted"><?= e(t('admin.import_csv_intro')) ?></p>
<form method="post" action="<?= path('admin/import/csv') ?>" class="admin-form box">
    <?= Csrf::field() ?>
    <div class="field-row">
        <div class="field"><label for="csv-source"><?= e(t('admin.platform')) ?></label>
            <select id="csv-source" name="source"><?php foreach ($sources as $s): ?><option value="<?= $s ?>"><?= e(platform_name($s)) ?></option><?php endforeach; ?></select></div>
        <div class="field"><label for="csv-country"><?= e(t('admin.country')) ?></label><select id="csv-country" name="country_id" required><?= $countryOptions(null) ?></select></div>
        <div class="field"><label for="csv-day"><?= e(t('admin.import_chart_date')) ?></label><input id="csv-day" type="date" name="observed_on" value="<?= e($today) ?>" max="<?= e($today) ?>" required></div>
    </div>
    <div class="field"><label for="csv-rows"><?= e(t('admin.import_rows_label')) ?></label>
        <textarea id="csv-rows" name="rows" rows="8" required placeholder="1;GTA;Seyi Vibez&#10;2;Baba;Hotkeed feat. Zlatan&#10;3;Migbo;Sethlo"></textarea>
        <p class="field__hint"><?= e(t('admin.import_rows_hint')) ?></p></div>
    <button class="button" type="submit"><?= e(t('admin.import_csv_button')) ?></button>
</form>
