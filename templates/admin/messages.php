<?php
/** @var array $rows */
use Cauri\Core\Csrf;
?>
<h1><?= e(t('admin.nav_messages')) ?></h1>
<p class="muted"><?= e(t('admin.messages_intro')) ?></p>
<?php if (!$rows): ?><p class="muted"><?= e(t('admin.none')) ?></p><?php endif; ?>
<?php foreach ($rows as $m): ?>
    <article class="box<?= $m['type'] === 'contestation' ? ' box--accent' : '' ?>">
        <p><strong><?= e($m['subject']) ?></strong> · <span class="tag"><?= e(t('contact.type_' . ($m['type'] === 'contestation' ? 'contest' : 'contact'))) ?></span>
            <span class="status status--<?= $m['status'] === 'new' ? 'pending' : 'ok' ?>"><?= e(t('admin.msg_' . $m['status'])) ?></span></p>
        <p class="muted"><?= e($m['name']) ?> · <a href="mailto:<?= e($m['email']) ?>"><?= e($m['email']) ?></a> · <?= e($m['created_at']) ?>
            <?php if ($m['type'] === 'contestation' && $m['status'] === 'new'): ?> · <?= e(t('admin.answer_before', ['date' => fmt_date(date('Y-m-d', strtotime($m['created_at'] . ' +7 days')))])) ?><?php endif; ?></p>
        <p><?= nl2br(e($m['message'])) ?></p>
        <form method="post" action="<?= path('admin/messages/' . $m['id']) ?>" class="toolbar">
            <?= Csrf::field() ?>
            <?php foreach (['answered', 'closed', 'new'] as $s): if ($s === $m['status']) continue; ?>
                <button class="button button--small button--ghost" name="status" value="<?= $s ?>" type="submit"><?= e(t('admin.mark_' . $s)) ?></button>
            <?php endforeach; ?>
        </form>
    </article>
<?php endforeach; ?>
