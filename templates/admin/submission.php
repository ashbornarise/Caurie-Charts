<?php
/** @var array $s @var array $tracks @var ?int $public */
use Cauri\Core\Csrf;

$breakdown = json_decode((string) $s['country_breakdown'], true) ?: [];
$gap = $public ? abs((int) $s['streams'] - $public) / max(1, $public) * 100 : null;
?>
<p><a href="<?= path('admin/declarations') ?>">← <?= e(t('admin.nav_submissions')) ?></a></p>
<h1><?= e($s['submitted_track_title']) ?> · <?= e($s['submitted_artist_name']) ?></h1>
<p><span class="status status--<?= e($s['status']) ?>"><?= e(t('admin.review_' . $s['status'])) ?></span>
    <?php if ($s['reviewer']): ?><span class="muted"><?= e($s['reviewer']) ?>, <?= e((string) $s['reviewed_at']) ?> : <?= e((string) $s['review_note']) ?></span><?php endif; ?></p>

<div class="two-cols">
    <div class="box">
        <dl>
            <dt><?= e(t('submit.platform')) ?></dt><dd><?= e(platform_name($s['platform'])) ?></dd>
            <dt><?= e(t('admin.period')) ?></dt><dd><?= e(fmt_date($s['period_start'])) ?> → <?= e(fmt_date($s['period_end'])) ?></dd>
            <dt><?= e(t('submit.streams')) ?></dt><dd><strong><?= e(fmt_number((int) $s['streams'])) ?></strong></dd>
            <dt><?= e(t('admin.public_data')) ?></dt>
            <dd><?= $public !== null ? e(fmt_number($public)) . ' (' . e(t('admin.gap', ['n' => fmt_number((float) $gap)])) . ')' : e(t('admin.no_public_data')) ?></dd>
            <dt><?= e(t('submit.breakdown')) ?></dt>
            <dd><?= $breakdown ? e(implode(', ', array_map(fn ($k, $v) => "$k $v %", array_keys($breakdown), $breakdown))) : '—' ?></dd>
            <dt><?= e(t('admin.contact')) ?></dt><dd><?= e($s['contact_name']) ?> · <a href="mailto:<?= e($s['contact_email']) ?>"><?= e($s['contact_email']) ?></a></dd>
        </dl>
    </div>
    <div class="box">
        <a href="<?= path('admin/declarations/' . $s['id'] . '/capture') ?>" target="_blank" rel="noopener">
            <img class="screenshot" src="<?= path('admin/declarations/' . $s['id'] . '/capture') ?>" alt="<?= e(t('submit.screenshot')) ?>">
        </a>
    </div>
</div>

<?php if ($s['status'] === 'pending'): ?>
<form method="post" action="<?= path('admin/declarations/' . $s['id']) ?>" class="admin-form box box--accent">
    <?= Csrf::field() ?>
    <div class="field"><label for="track_id"><?= e(t('admin.link_track')) ?></label>
        <select id="track_id" name="track_id">
            <option value=""><?= e(t('form.choose')) ?></option>
            <?php foreach ($tracks as $t): ?>
                <option value="<?= (int) $t['id'] ?>" <?= (int) $t['id'] === (int) $s['track_id'] ? 'selected' : '' ?>><?= e($t['artist_name'] . ' · ' . $t['title']) ?></option>
            <?php endforeach; ?>
        </select>
        <p class="field__hint"><?= e(t('admin.link_track_hint')) ?></p>
    </div>
    <div class="field"><label for="note"><?= e(t('admin.note')) ?></label><textarea id="note" name="note" rows="2"></textarea></div>
    <div class="decision__buttons">
        <button class="button" name="decision" value="validated" type="submit"><?= e(t('admin.validate')) ?></button>
        <button class="button button--danger" name="decision" value="rejected" type="submit"><?= e(t('admin.reject')) ?></button>
    </div>
</form>
<?php endif; ?>
