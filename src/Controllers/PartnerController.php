<?php

namespace Cauri\Controllers;

use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Repositories\PartnerRepository;

/** Page publique des partenaires officiels. */
final class PartnerController extends Controller
{
    public function index(Request $request): Response
    {
        $this->useLocale();
        return $this->page('partners-page', [
            'partners' => (new PartnerRepository($this->db))->active(),
            'meta'     => [
                'title'       => t('partners.title') . ' · ' . brand(),
                'description' => t('partners.meta_description', ['brand' => brand()]),
            ],
        ]);
    }
}
