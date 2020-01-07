import random

import torch
import torch.utils.data as tud
from torch import optim

from util_ops import bbox2mask, brush_stroke_mask, random_bbox, gan_hinge_loss
from discriminator import Discriminator
from generator import Generator
from visual_ops import plot_losses


class GAN:
    def __init__(self, device):
        self.device = device
        self.dtype = torch.float32
        self.gen = Generator().to(device)
        self.dis = Discriminator().to(device)

        # Hyperparameters
        self.num_epochs = 10
        self.batch_size = 4

        self.lr = 1e-4  # 0.0002
        self.beta1 = 0.5
        self.beta2 = 0.999
        self.l1_loss_alpha = 1

        # Establish convention for real and fake labels during training
        self.real_label = 1
        self.fake_label = -1

        # Setup Adam optimizers for both G and D
        self.optimizerD = optim.Adam(self.dis.parameters(), lr=self.lr, betas=(self.beta1, self.beta2))
        self.optimizerG = optim.Adam(self.gen.parameters(), lr=self.lr, betas=(self.beta1, self.beta2))

    def train_gan(self, dataset):
        # Create the dataloader
        dataloader = tud.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        G_losses = []
        D_losses = []
        iters = 0
        self.gen.train()
        self.dis.train()
        for epoch in range(self.num_epochs):
            for i, batch_data in enumerate(dataloader, 0):
                # Prepare batch
                batch_real = batch_data[0].to(self.device)
                bbox = random_bbox()
                regular_mask = bbox2mask(bbox)
                irregular_mask = brush_stroke_mask()
                mask = random.choice([regular_mask, irregular_mask]).to(self.device)
                batch_incomplete = (batch_real * (torch.tensor(1., device=self.device) - mask)).to(self.device)
                xin = batch_incomplete
                # Discriminator forward pass and GAN loss
                self.dis.zero_grad()
                # Generator output
                x1, x2, _ = self.gen(xin, mask)
                batch_predicted = x2
                batch_fake = (batch_predicted * mask + batch_incomplete * (torch.tensor(1.) - mask)).to(self.device)
                batch_mixed = torch.cat([batch_real, batch_fake], dim=0).to(self.device)
                batch_mixed = torch.cat((batch_mixed, torch.cat((mask,) * self.batch_size * 2)), dim=1).to(self.device)
                # Discriminator output for both real and fake images
                labels_mixed = self.dis(batch_mixed)
                labels_pos, labels_neg = torch.split(labels_mixed, labels_mixed.shape[0] // 2)
                _, d_loss = gan_hinge_loss(labels_pos, labels_neg, self.device)
                dis_loss = d_loss
                D_losses.append(d_loss.item())
                d_loss.backward(retain_graph=True)
                self.optimizerD.step()
                # Generator l1 and GAN loss
                self.gen.zero_grad()
                l1_loss = self.l1_loss_alpha * (torch.mean(torch.abs(batch_real - x1)) +
                                                torch.mean(torch.abs(batch_real - x2)))
                l1_loss = l1_loss
                # Discriminator output for only fake images
                batch_fake = torch.cat((batch_fake, torch.cat((mask,) * self.batch_size)), dim=1)
                labels_neg = self.dis(batch_fake)
                g_loss = -torch.mean(labels_neg)
                gen_loss = g_loss
                g_loss = g_loss.to(self.device)
                G_losses.append(g_loss.item())
                g_loss = g_loss + l1_loss
                g_loss.backward()
                self.optimizerG.step()
                #if iters % 100 == 0:
                print("Epoch {:2d}/{:2d}, iteration {:<4d}: g_loss = {:.5f}, d_loss = {:.5f}"
                      .format(epoch + 1, self.num_epochs, iters + 1, gen_loss.item(), dis_loss.item()))
                iters += 1

        plot_losses(G_losses, D_losses)


    def inpaint_image(self, image, mask):
        image_incomplete = image * (torch.tensor(1.) - mask)
        _, prediction, _ = self.gen(image_incomplete, mask)
        return prediction
