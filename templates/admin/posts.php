<?php
/** @var array $posts @var string $exportDir */
use Cauri\Core\Csrf;

$themes = ['classement' => 'Tendances', 'artiste' => 'Artiste de la semaine', 'weekend' => 'Spécial week-end'];
$media = fn (?string $f) => $f ? '/media/social/' . rawurlencode(basename($f)) : null;
?>
<h1><?= e(t('admin.nav_posts')) ?></h1>
<p class="muted"><?= e(t('admin.posts_intro')) ?></p>
<?php if ($exportDir): ?><p class="muted"><?= e(t('admin.posts_folder', ['dir' => $exportDir])) ?></p><?php endif; ?>

<form method="post" action="<?= path('admin/posts/generer') ?>" class="toolbar box box--accent">
    <?= Csrf::field() ?>
    <strong><?= e(t('admin.posts_generate')) ?></strong>
    <button class="button button--small" name="theme" value="tous" type="submit"><?= e(t('admin.posts_generate_all')) ?></button>
    <?php foreach ($themes as $k => $label): ?>
        <button class="button button--small button--ghost" name="theme" value="<?= $k ?>" type="submit"><?= e($label) ?></button>
    <?php endforeach; ?>
    <small class="muted"><?= e(t('admin.posts_generate_note')) ?></small>
</form>

<?php if (!$posts): ?><p class="empty"><?= e(t('admin.posts_none')) ?></p><?php endif; ?>
<div class="posts">
<?php foreach ($posts as $p): ?>
    <article class="post-card post-card--<?= e($p['status']) ?>" id="post-<?= (int) $p['id'] ?>">
        <header class="post-card__head">
            <div>
                <span class="tag"><?= e($themes[$p['theme']] ?? $p['theme']) ?></span>
                <small class="muted"><?= e(fmt_date($p['slot_date'])) ?></small>
                <h2 class="post-card__title"><?= e($p['title']) ?></h2>
            </div>
            <span class="status status--<?= $p['status'] === 'published' ? 'published' : ($p['status'] === 'rejected' ? 'rejected' : 'draft') ?>"><?= e(t('admin.post_status_' . $p['status'])) ?></span>
        </header>

        <?php if ($p['slides']): ?>
        <ol class="post-card__slides">
            <?php foreach ($p['slides'] as $i => $s): ?>
            <li><a href="<?= e($media($s['file'])) ?>" target="_blank" rel="noopener" title="<?= e($s['label']) ?>">
                <img src="<?= e($media($s['file'])) ?>" alt="<?= e($s['label'] ?: 'Diapositive ' . ($i + 1)) ?>" loading="lazy" width="120" height="150">
                <span><?= sprintf('%02d', $i + 1) ?></span>
            </a></li>
            <?php endforeach; ?>
        </ol>
        <?php endif; ?>
        <p class="post-card__files">
            <?php if ($p['image_square']): ?><a href="<?= e($media($p['image_square'])) ?>" target="_blank" rel="noopener"><?= e(t('admin.post_square')) ?></a><?php endif; ?>
            <?php if ($p['image_story']): ?><a href="<?= e($media($p['image_story'])) ?>" target="_blank" rel="noopener"><?= e(t('admin.post_story')) ?></a><?php endif; ?>
            <?php if ($p['video']): ?><a href="<?= e($media($p['video'])) ?>" target="_blank" rel="noopener"><?= e(t('admin.post_video')) ?></a><?php endif; ?>
        </p>

        <label class="post-card__caption-label" for="caption-<?= (int) $p['id'] ?>"><?= e(t('admin.post_caption')) ?></label>
        <textarea class="post-card__caption" id="caption-<?= (int) $p['id'] ?>" rows="8" readonly><?= e($p['caption'] . "\n\n" . $p['hashtags']) ?></textarea>
        <div class="toolbar">
            <button class="button button--small" type="button" data-copy="caption-<?= (int) $p['id'] ?>"><?= e(t('admin.post_copy')) ?></button>
            <form method="post" action="<?= path('admin/posts/' . $p['id']) ?>" class="toolbar">
                <?= Csrf::field() ?>
                <?php if ($p['status'] !== 'published'): ?><button class="button button--small button--ghost" name="status" value="published" type="submit"><?= e(t('admin.post_mark_published')) ?></button><?php endif; ?>
                <?php if ($p['status'] !== 'rejected'): ?><button class="button button--small button--ghost" name="status" value="rejected" type="submit"><?= e(t('admin.post_reject')) ?></button><?php endif; ?>
                <?php if ($p['status'] !== 'draft'): ?><button class="button button--small button--ghost" name="status" value="draft" type="submit"><?= e(t('admin.post_back_draft')) ?></button><?php endif; ?>
            </form>
        </div>
    </article>
<?php endforeach; ?>
</div>
