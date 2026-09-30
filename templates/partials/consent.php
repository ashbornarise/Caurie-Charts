<?php
/** Bandeau de consentement : affiché seulement si Google Analytics ou Meta Pixel est configuré. */
use Cauri\Core\Config;

$t = Config::get('app.tracking');
?>
<div id="consent" class="consent" role="dialog" aria-labelledby="consent-title" aria-describedby="consent-text" hidden>
    <div class="consent__inner">
        <h2 id="consent-title" class="consent__title"><?= e(t('consent.title')) ?></h2>
        <p id="consent-text"><?= e(t('consent.text', ['brand' => brand()])) ?> <a href="<?= path('cookies') ?>"><?= e(t('consent.more')) ?></a></p>

        <div class="consent__panel" data-consent-panel hidden>
            <label class="consent__option consent__option--locked">
                <input type="checkbox" checked disabled>
                <span><strong><?= e(t('consent.cat_necessary')) ?></strong> <?= e(t('consent.cat_necessary_text')) ?></span>
            </label>
            <?php if ($t['ga_id']): ?>
            <label class="consent__option"><input type="checkbox" name="analytics">
                <span><strong><?= e(t('consent.cat_analytics')) ?></strong> <?= e(t('consent.cat_analytics_text')) ?></span></label>
            <?php endif; ?>
            <?php if ($t['meta_pixel_id']): ?>
            <label class="consent__option"><input type="checkbox" name="ads">
                <span><strong><?= e(t('consent.cat_ads')) ?></strong> <?= e(t('consent.cat_ads_text')) ?></span></label>
            <?php endif; ?>
            <?php if ($t['youtube_embeds']): ?>
            <label class="consent__option"><input type="checkbox" name="media">
                <span><strong><?= e(t('consent.cat_media')) ?></strong> <?= e(t('consent.cat_media_text')) ?></span></label>
            <?php endif; ?>
            <button class="button button--small" type="button" data-consent-save><?= e(t('consent.save')) ?></button>
        </div>

        <div class="consent__actions">
            <button class="button button--ghost" type="button" data-consent-refuse><?= e(t('consent.refuse')) ?></button>
            <button class="button button--ghost" type="button" data-consent-custom aria-expanded="false"><?= e(t('consent.customize')) ?></button>
            <button class="button button--ghost" type="button" data-consent-accept><?= e(t('consent.accept')) ?></button>
        </div>
    </div>
</div>
