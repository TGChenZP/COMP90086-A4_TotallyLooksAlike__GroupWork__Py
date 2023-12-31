from model.__template__ import *
from model.Modules import *

class CNN_Siamise_Triplet(CNN_Triplet_Model):
    class Model(nn.Module):
                
        def __init__(self, CFG):
            super().__init__()
            self.CFG = CFG

            assert not (self.CFG.freeze_encoder and not self.CFG.pretrained), "If encoder is frozen, it must be pretrained"

            torch.manual_seed(self.CFG.random_state)

            self.encoder = torch.hub.load('pytorch/vision:v0.10.0', self.CFG.encoder, pretrained=self.CFG.pretrained) if type(self.CFG.encoder) == str else self.CFG.encoder # load the model

            if self.CFG.crop_pretrained_linear:
                self.encoder = nn.Sequential(*list(self.encoder.children())[:-1]) # crop the last layer if set to true

            # get example output size to know size of flatten layer
            sample_input = torch.randn([1, self.CFG.input_shape[1], self.CFG.input_shape[2], self.CFG.input_shape[3]])  
            sample_output = self.encoder(sample_input)

            flatten_shape = np.prod(sample_output.shape[1:])

            # consider freezing parameters
            for param in self.encoder.parameters():
                param.requires_grad = not self.CFG.freeze_encoder

            # get MLP layers for after CNN
            if self.CFG.num_mlp_layers:
                
                self.transition_encoder = nn.Linear(flatten_shape, self.CFG.hidden_dim)

                if self.CFG.res_learning:
                    self.mlp_encoding = nn.ModuleList([ResLayer(self.CFG) for _ in range(self.CFG.num_mlp_layers-1)]) # -1 layer because of transition layer
                else:
                    self.mlp_encoding = nn.ModuleList([LinearLayer(self.CFG) for _ in range(self.CFG.num_mlp_layers-1)])

                self.out_encoding = nn.Linear(self.CFG.hidden_dim, self.CFG.embed_dim)

            else:
                self.out_encoding = nn.Linear(flatten_shape, self.CFG.embed_dim)

            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(self.CFG.dropout)
        
            
        def forward(self, x_anchor = None, x_positive = None, x_negative = None):
            
            if x_anchor is not None and x_positive is not None and x_negative is not None:
                x_anchor = x_anchor.permute(0, 3, 1, 2) # change axis order
                x_positive = x_positive.permute(0, 3, 1, 2)
                x_negative = x_negative.permute(0, 3, 1, 2)

                x_anchor = self.encoder(x_anchor)
                x_positive = self.encoder(x_positive)
                x_negative = self.encoder(x_negative)

                batch_size = x_anchor.size(0)
                
                x_anchor = x_anchor.reshape(batch_size, -1) # flatten out the encoded image
                x_positive = x_positive.reshape(batch_size, -1)
                x_negative = x_negative.reshape(batch_size, -1)

                if self.CFG.num_mlp_layers:
                    x_anchor = self.dropout(self.relu(self.transition_encoder(x_anchor))) # first go through resizing layer to change flatten_size to hidden dim
                    x_positive = self.dropout(self.relu(self.transition_encoder(x_positive)))
                    x_negative = self.dropout(self.relu(self.transition_encoder(x_negative)))

                    for layer in self.mlp_encoding: # go through mlp layers
                        x_anchor = layer(x_anchor)
                        x_positive = layer(x_positive)
                        x_negative = layer(x_negative)
                
                if self.CFG.final_relu:
        
                    return self.relu(self.out_encoding(x_anchor)), self.relu(self.out_encoding(x_positive)), self.relu(self.out_encoding(x_negative)) # export embedding

                else:
                        
                    return self.out_encoding(x_anchor), self.out_encoding(x_positive), self.out_encoding(x_negative)

            # eval mode: anchor
            elif x_anchor is not None and x_positive is None and x_negative is None:
                x_anchor = x_anchor.permute(0, 3, 1, 2) # change axis order

                x_anchor = self.encoder(x_anchor)

                batch_size = x_anchor.size(0)
                
                x_anchor = x_anchor.reshape(batch_size, -1) # flatten out the encoded image

                if self.CFG.num_mlp_layers:
                    x_anchor = self.dropout(self.relu(self.transition_encoder(x_anchor))) # first go through resizing layer to change flatten_size to hidden dim

                    for layer in self.mlp_encoding: # go through mlp layers
                        x_anchor = layer(x_anchor)

                if self.CFG.final_relu:
        
                    return self.relu(self.out_encoding(x_anchor))
                else:
                    return self.out_encoding(x_anchor)

            # eval mode: positive
            elif x_positive is not None and x_anchor is None and x_negative is None:
                x_positive = x_positive.permute(0, 3, 1, 2)

                x_positive = self.encoder(x_positive)

                batch_size = x_positive.size(0)
                
                x_positive = x_positive.reshape(batch_size, -1)

                if self.CFG.num_mlp_layers:
                    x_positive = self.dropout(self.relu(self.transition_encoder(x_positive)))

                    for layer in self.mlp_encoding:
                        x_positive = layer(x_positive)
                

                if self.CFG.final_relu:
                    return self.relu(self.out_encoding(x_positive))
                else:
                    return self.out_encoding(x_positive)
        
    def __init__(self, CFG, name="CNN_Siamise_Triplet"):
        super().__init__(CFG, name=CFG.name)